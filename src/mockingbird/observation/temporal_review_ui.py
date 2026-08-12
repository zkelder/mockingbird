"""Self-contained, human-authoritative localization review page renderer."""

from __future__ import annotations

from html import escape
import json
from typing import Any


def render_review_ui(
    manifest: dict[str, Any],
    frames: list[dict[str, Any]],
    crop_paths: list[str],
    annotation_payload: dict[str, Any],
) -> str:
    """Render a local-only UI; model overlays are suggestions, never truth."""

    rows: list[str] = []
    for index, (record, crop_name) in enumerate(zip(frames, crop_paths)):
        frame_id = escape(str(record["frame_id"]), quote=True)
        source_directory = (
            "high-resolution" if record.get("high_resolution") else "frames"
        )
        source_path = f"{source_directory}/{frame_id}.jpg"
        triggers = escape(", ".join(record["trigger_reasons"]))
        rows.append(
            f"<section class='frame' id='review-{index}'>"
            f"<h2>{frame_id}</h2>"
            "<div class='images'>"
            "<figure><figcaption>Actual retained image — draw human boxes here</figcaption>"
            f"<div class='canvas-wrap'><img class='source' data-index='{index}' src='{source_path}' "
            f"alt='Retained frame {frame_id}'/><canvas data-index='{index}'></canvas></div></figure>"
            "<figure><figcaption>Non-authoritative detector/proposal suggestions</figcaption>"
            f"<img class='suggestion' src='crops/{escape(crop_name, quote=True)}' "
            f"alt='Model suggestion overlay for {frame_id}' loading='lazy'/></figure></div>"
            f"<p>offset={record['source_offset_ms']}ms · sequence={record['sequence']} · "
            f"generation={escape(str(record['provider_generation']))} · triggers={triggers}</p>"
            "<div class='controls'>"
            f"<button type='button' data-truth='yes' onclick=\"markFrame({index},'yes')\">Animal</button>"
            f"<button type='button' data-truth='no' onclick=\"markFrame({index},'no')\">No animal</button>"
            f"<button type='button' data-truth='ambiguous' onclick=\"markFrame({index},'ambiguous')\">Ambiguous</button>"
            f"<button type='button' onclick='undoBox({index})'>Undo box</button>"
            f"<button type='button' onclick='clearBoxes({index})'>Clear boxes</button>"
            f"<span class='status' data-index='{index}'></span></div></section>"
        )

    state_json = json.dumps(annotation_payload, sort_keys=True).replace("</", "<\\/")
    session_id = escape(str(manifest.get("session_id", "")), quote=True)
    return f"""<!doctype html><html><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Temporal localization review: {session_id}</title>
<style>
body{{font:15px system-ui,sans-serif;margin:0;background:#101317;color:#eeeeee}}
header{{position:sticky;top:0;z-index:5;background:#18202a;padding:12px 18px;border-bottom:1px solid #445}}
.frame{{padding:16px 18px;border-bottom:1px solid #39414d}} .images{{display:flex;gap:18px;flex-wrap:wrap}}
figure{{margin:0;max-width:900px}} figcaption{{margin:0 0 6px;color:#cbd5e1}}
.canvas-wrap{{position:relative;line-height:0}} .source{{display:block;max-width:min(900px,95vw);height:auto}}
canvas{{position:absolute;inset:0;width:100%;height:100%;cursor:crosshair}} .suggestion{{max-width:min(560px,90vw)}}
.controls{{display:flex;gap:8px;align-items:center;flex-wrap:wrap}} button,input{{font:inherit;padding:7px 10px}}
button.selected{{outline:3px solid #f6c344}} .status{{color:#9fe3b2}} .warning{{color:#ffcf7d}}
</style></head><body>
<header><strong>Human localization review</strong> · session {session_id} · {len(frames)} frames
<label> Reviewer <input id='reviewer' placeholder='name or initials' autocomplete='name'></label>
<button type='button' onclick='downloadAnnotations()'>Download annotation.json</button>
<span id='global-status' class='warning'>Select truth for each frame; animal frames require at least one human box.</span>
<p>Only the actual image is authoritative. Red/blue suggestion overlays are context and are never copied into truth.</p></header>
{"".join(rows)}
<script>
const annotations={state_json};
const boxes=annotations.frames.map(frame => (frame.boxes || []).map(item => item.box));
const starts={{}};
function frameState(i){{return annotations.frames[i]}}
function setProvenance(i){{
  const reviewer=document.getElementById('reviewer').value.trim();
  if(!reviewer) return false;
  frameState(i).provenance={{reviewer,reviewed_at_iso:new Date().toISOString(),
    source_capture_session:annotations.capture_session_id,truth_source:'full_frame_inspection',
    product_review_label:null,whole_frame_independently_confirmed:true}};
  return true;
}}
function markFrame(i,truth){{
  if(!setProvenance(i)){{alert('Enter the human reviewer name or initials first.');return}}
  const frame=frameState(i); frame.whole_frame_truth=truth; frame.yes_but_unscorable=false;
  if(truth!=='yes'){{boxes[i]=[];frame.boxes=[]}}
  update(i);
}}
function normalizedPoint(event,canvas){{const r=canvas.getBoundingClientRect();return [
  Math.max(0,Math.min(1,(event.clientX-r.left)/r.width)),
  Math.max(0,Math.min(1,(event.clientY-r.top)/r.height))]}}
function redraw(i){{
  const canvas=document.querySelector(`canvas[data-index="${{i}}"]`); if(!canvas.width)return;
  const context=canvas.getContext('2d');context.clearRect(0,0,canvas.width,canvas.height);
  context.strokeStyle='#53f28b';context.lineWidth=Math.max(2,canvas.width/450);
  boxes[i].forEach(box=>context.strokeRect(box[0]*canvas.width,box[1]*canvas.height,
    (box[2]-box[0])*canvas.width,(box[3]-box[1])*canvas.height));
}}
function update(i){{
  const frame=frameState(i);frame.boxes=boxes[i].map(box=>({{box,broad_class:'animal',partially_visible:false,
    occluded:false,edge_clipped:false,blurred:false,distance:null,box_confidence:'confident',review_limitation:null}}));
  const section=document.getElementById(`review-${{i}}`);
  section.querySelectorAll('[data-truth]').forEach(button=>button.classList.toggle('selected',button.dataset.truth===frame.whole_frame_truth));
  section.querySelector('.status').textContent=`${{frame.whole_frame_truth}} · ${{boxes[i].length}} human box(es)`;redraw(i);
}}
function undoBox(i){{boxes[i].pop();update(i)}} function clearBoxes(i){{boxes[i]=[];update(i)}}
document.querySelectorAll('img.source').forEach(img=>img.addEventListener('load',()=>{{
  const i=Number(img.dataset.index),canvas=document.querySelector(`canvas[data-index="${{i}}"]`);
  const width=Math.min(900,img.naturalWidth);canvas.width=width;canvas.height=Math.round(width*img.naturalHeight/img.naturalWidth);update(i);
}}));
document.querySelectorAll('canvas').forEach(canvas=>{{
  const i=Number(canvas.dataset.index);canvas.addEventListener('pointerdown',event=>{{starts[i]=normalizedPoint(event,canvas);canvas.setPointerCapture(event.pointerId)}});
  canvas.addEventListener('pointerup',event=>{{if(!starts[i])return;const end=normalizedPoint(event,canvas),start=starts[i];delete starts[i];
    const box=[Math.min(start[0],end[0]),Math.min(start[1],end[1]),Math.max(start[0],end[0]),Math.max(start[1],end[1])];
    if(box[2]-box[0]>.003&&box[3]-box[1]>.003){{boxes[i].push(box);frameState(i).whole_frame_truth='yes';setProvenance(i);update(i)}}
  }});
}});
function downloadAnnotations(){{
  const reviewer=document.getElementById('reviewer').value.trim();if(!reviewer){{alert('Enter the reviewer name or initials.');return}}
  for(let i=0;i<annotations.frames.length;i++){{const frame=frameState(i);if(frame.whole_frame_truth==='unreviewed'){{alert(`Frame ${{frame.frame_id}} is unreviewed.`);return}}
    if(frame.whole_frame_truth==='yes'&&!boxes[i].length){{alert(`Animal frame ${{frame.frame_id}} needs a human bounding box.`);return}}setProvenance(i);update(i)}}
  const blob=new Blob([JSON.stringify(annotations,null,2)+'\\n'],{{type:'application/json'}}),link=document.createElement('a');
  link.href=URL.createObjectURL(blob);link.download='annotation.json';link.click();URL.revokeObjectURL(link.href);
  document.getElementById('global-status').textContent='Downloaded. Replace this packet’s annotation.json, then run temporal-review-validate.';
}}
</script></body></html>"""


__all__ = ["render_review_ui"]
