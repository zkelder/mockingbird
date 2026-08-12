"""Self-contained, human-authoritative localization review page renderer.

Serves both the original Stage 6.6 single-session reviewer and the Stage-3
correction-tranche reviewer (`temporal_review_io.build_stage3_tranche_
review_packet`) from one template: Stage-3-only context (tranche/lane/
priority tier/split candidate, difficulty tags) is rendered only when a
frame record actually carries it, so the original flow's page is unchanged
aside from the shared navigation/durability/ergonomics improvements below.
"""

from __future__ import annotations

from html import escape
import json
from typing import Any

from mockingbird.observation.temporal_annotation import DIFFICULTY_TAGS


def render_review_ui(
    manifest: dict[str, Any],
    frames: list[dict[str, Any]],
    crop_paths: list[str],
    annotation_payload: dict[str, Any],
) -> str:
    """Render a local-only UI; model overlays are suggestions, never truth.

    Ergonomics: one frame focused at a time with next/previous navigation
    and keyboard shortcuts, a progress count, an optional non-authoritative
    suggestion-overlay toggle, per-box select+delete (not only undo-last),
    optional difficulty-tag quick-select, and localStorage autosave/resume
    plus an explicit "Load annotation.json" import -- so a ~700-image review
    effort survives a browser/process restart without losing work. The
    existing "Download annotation.json" export remains the one authoritative
    hand-off into `temporal-review-validate`.
    """

    rows: list[str] = []
    for index, (record, crop_name) in enumerate(zip(frames, crop_paths)):
        frame_id = escape(str(record["frame_id"]), quote=True)
        source_directory = (
            "high-resolution" if record.get("high_resolution") else "frames"
        )
        source_path = f"{source_directory}/{frame_id}.jpg"
        triggers = escape(", ".join(record["trigger_reasons"]))
        tranche_line = _tranche_context_line(record)
        difficulty_chips = "".join(
            f"<button type='button' class='tag-chip' data-tag='{tag}' "
            f"onclick=\"toggleDifficultyTag({index},'{tag}')\">{escape(tag.replace('_', ' '))}</button>"
            for tag in DIFFICULTY_TAGS
        )
        rows.append(
            f"<section class='frame hidden' id='review-{index}' data-index='{index}' "
            f"data-lane='{escape(str(record.get('stage3_target_lane') or ''), quote=True)}'>"
            f"<h2>{frame_id}</h2>"
            f"{tranche_line}"
            "<div class='images'>"
            "<figure><figcaption>Actual retained image — draw human boxes here</figcaption>"
            f"<div class='canvas-wrap'><img class='source' data-index='{index}' src='{source_path}' loading='lazy' "
            f"alt='Retained frame {frame_id}'/><canvas data-index='{index}'></canvas></div></figure>"
            "<figure class='suggestion-figure'><figcaption>Non-authoritative detector/proposal suggestions "
            "(toggle in the header; never copied into truth)</figcaption>"
            f"<img class='suggestion' data-index='{index}' src='crops/{escape(crop_name, quote=True)}' "
            f"alt='Model suggestion overlay for {frame_id}' loading='lazy'/></figure></div>"
            f"<p>offset={record['source_offset_ms']}ms · sequence={record['sequence']} · "
            f"generation={escape(str(record['provider_generation']))} · triggers={triggers}</p>"
            "<div class='controls'>"
            f"<button type='button' data-truth='yes' onclick=\"markFrame({index},'yes')\">Animal</button>"
            f"<button type='button' data-truth='no' onclick=\"markFrame({index},'no')\">No animal</button>"
            f"<button type='button' data-truth='ambiguous' onclick=\"markFrame({index},'ambiguous')\">Ambiguous</button>"
            f"<button type='button' onclick='undoBox({index})'>Undo box</button>"
            f"<button type='button' onclick='deleteSelectedBox({index})'>Delete selected box</button>"
            f"<button type='button' onclick='clearBoxes({index})'>Clear boxes</button>"
            f"<span class='status' data-index='{index}'></span></div>"
            f"<div class='tags'><span class='tags-label'>Difficulty tags (optional):</span>{difficulty_chips}</div>"
            "<div class='note'><label>Reviewer note "
            f"<input type='text' class='note-input' data-index='{index}' maxlength='2000' "
            f"oninput=\"setNote({index}, this.value)\"></label></div>"
            "</section>"
        )

    state_json = json.dumps(annotation_payload, sort_keys=True).replace("</", "<\\/")
    session_id = escape(str(manifest.get("session_id", "")), quote=True)
    tranche_header = _tranche_header_note(frames)
    return f"""<!doctype html><html><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Temporal localization review: {session_id}</title>
<style>
body{{font:15px system-ui,sans-serif;margin:0;background:#101317;color:#eeeeee}}
header{{position:sticky;top:0;z-index:5;background:#18202a;padding:10px 18px;border-bottom:1px solid #445}}
header .row{{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:4px 0}}
.frame{{padding:16px 18px;border-bottom:1px solid #39414d}} .frame.hidden{{display:none}}
.images{{display:flex;gap:18px;flex-wrap:wrap}}
figure{{margin:0;max-width:900px}} figcaption{{margin:0 0 6px;color:#cbd5e1}}
body.hide-suggestions .suggestion-figure{{display:none}}
.canvas-wrap{{position:relative;line-height:0}} .source{{display:block;max-width:min(900px,95vw);height:auto}}
canvas{{position:absolute;inset:0;width:100%;height:100%;cursor:crosshair}} .suggestion{{max-width:min(560px,90vw)}}
.controls{{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:8px}} button,input,textarea{{font:inherit;padding:7px 10px}}
button.selected{{outline:3px solid #f6c344}} .status{{color:#9fe3b2}} .warning{{color:#ffcf7d}}
.tags{{margin-top:10px;display:flex;gap:6px;flex-wrap:wrap;align-items:center}} .tags-label{{color:#9fb0c3}}
.tag-chip{{background:#1c2530;color:#cfd8e3;border:1px solid #445;border-radius:14px;padding:4px 10px;font-size:13px;cursor:pointer}}
.tag-chip.selected{{background:#3a5a3a;border-color:#6bcB6b;color:#fff}}
.note{{margin-top:8px}} .note-input{{width:min(600px,90vw)}}
.tranche-line{{color:#9fd3ff;font-size:13px;margin:2px 0}}
.shortcuts{{color:#8393a6;font-size:12px}}
#frame-counter{{font-variant-numeric:tabular-nums;min-width:9em;display:inline-block}}
.navbtn{{font-size:16px}}
</style></head><body>
<header>
<div class='row'><strong>Human localization review</strong> · session {session_id}{tranche_header}
<span id='progress'></span></div>
<div class='row'>
<button type='button' class='navbtn' onclick='goTo(currentIndex-1)'>&#9664; Previous</button>
<span id='frame-counter'></span>
<button type='button' class='navbtn' onclick='goTo(currentIndex+1)'>Next &#9654;</button>
<button type='button' onclick='jumpToNextUnreviewed()'>Jump to next unreviewed</button>
<button type='button' id='toggle-suggestions-btn' onclick='toggleSuggestions()'>Hide suggestions</button>
</div>
<div class='row'>
<label> Reviewer <input id='reviewer' placeholder='name or initials' autocomplete='name'></label>
<button type='button' onclick='downloadAnnotations()'>Download annotation.json</button>
<label class='load-label'>Load annotation.json&hellip; <input id='load-file' type='file' accept='application/json'></label>
<span id='save-indicator' class='status'></span>
</div>
<p>Only the actual image is authoritative. Suggestion overlays are context and are never copied into truth.</p>
<span id='global-status' class='warning'>Select truth for each frame; animal frames require at least one human box.</span>
<p class='shortcuts'>Shortcuts: a=Animal · n=No animal · m=Ambiguous · &larr;/&rarr; or j/k=navigate · Enter/s=save &amp; advance ·
o=toggle suggestions · Delete/Backspace=remove selected box</p>
</header>
{"".join(rows)}
<script>
const FRAME_COUNT = {len(frames)};
const annotations={state_json};
const boxes=annotations.frames.map(frame => (frame.boxes || []).map(item => item.box));
const selected={{}};
const starts={{}};
let currentIndex=0;

function storageKey(){{return 'mockingbird-temporal-review:'+(annotations.capture_manifest_fingerprint||annotations.capture_session_id||'unknown')}}
function cursorKey(){{return storageKey()+':cursor'}}
function reviewedCount(a){{return a.frames.filter(f=>f.whole_frame_truth!=='unreviewed').length}}

function loadPersistedState(){{
  let stored=null;
  try {{ const raw=localStorage.getItem(storageKey()); if(raw) stored=JSON.parse(raw); }} catch(error) {{ stored=null; }}
  // Never silently lose more-complete progress: prefer whichever of the
  // embedded packet and localStorage has reviewed more frames. A freshly
  // regenerated packet (same fingerprint, e.g. after temporal-review-
  // validate ran against a hand-edited file) with *more* reviewed frames
  // than the browser's own cache wins; otherwise the local cache resumes.
  if (stored && stored.capture_manifest_fingerprint===annotations.capture_manifest_fingerprint
      && reviewedCount(stored) >= reviewedCount(annotations)) {{
    applyState(stored, {{persist:false}});
  }}
  const reviewer = localStorage.getItem('mockingbird-review-reviewer-name');
  if (reviewer) document.getElementById('reviewer').value = reviewer;
  if (localStorage.getItem('mockingbird-review-hide-suggestions')==='1') {{
    document.body.classList.add('hide-suggestions');
    document.getElementById('toggle-suggestions-btn').textContent='Show suggestions';
  }}
  let cursor=0;
  try {{ cursor=parseInt(localStorage.getItem(cursorKey())||'0',10)||0; }} catch(error) {{ cursor=0; }}
  currentIndex = Math.min(Math.max(0,cursor), FRAME_COUNT-1);
}}

function applyState(nextAnnotations, opts){{
  annotations.frames = nextAnnotations.frames;
  annotations.appearances = nextAnnotations.appearances || annotations.appearances;
  for (let i=0;i<FRAME_COUNT;i++) {{
    boxes[i] = (frameState(i).boxes || []).map(item => item.box);
    delete selected[i];
  }}
  if (!opts || opts.persist!==false) persist();
  for (let i=0;i<FRAME_COUNT;i++) update(i);
}}

function persist(){{
  try {{
    localStorage.setItem(storageKey(), JSON.stringify(annotations));
    const indicator=document.getElementById('save-indicator');
    if (indicator) {{ indicator.textContent='saved locally'; setTimeout(()=>{{ if(indicator.textContent==='saved locally') indicator.textContent=''; }}, 1500); }}
  }} catch (error) {{
    const indicator=document.getElementById('save-indicator');
    if (indicator) indicator.textContent='local save failed: '+error;
  }}
}}

function frameState(i){{return annotations.frames[i]}}

function setProvenance(i){{
  const reviewer=document.getElementById('reviewer').value.trim();
  if(!reviewer) return false;
  localStorage.setItem('mockingbird-review-reviewer-name', reviewer);
  frameState(i).provenance={{reviewer,reviewed_at_iso:new Date().toISOString(),
    source_capture_session:annotations.capture_session_id,truth_source:'full_frame_inspection',
    product_review_label:null,whole_frame_independently_confirmed:true}};
  return true;
}}

function markFrame(i,truth){{
  if(!setProvenance(i)){{alert('Enter the human reviewer name or initials first.');return}}
  const frame=frameState(i); frame.whole_frame_truth=truth; frame.yes_but_unscorable=false;
  if(truth!=='yes'){{boxes[i]=[];frame.boxes=[]}}
  delete selected[i];
  update(i); persist();
}}

function setNote(i,value){{ frameState(i).reviewer_note=value; persist(); }}

function toggleDifficultyTag(i,tag){{
  const frame=frameState(i);
  const current = frame.difficulty_tags || [];
  frame.difficulty_tags = current.includes(tag) ? current.filter(item=>item!==tag) : [...current, tag];
  update(i); persist();
}}

function normalizedPoint(event,canvas){{const r=canvas.getBoundingClientRect();return [
  Math.max(0,Math.min(1,(event.clientX-r.left)/r.width)),
  Math.max(0,Math.min(1,(event.clientY-r.top)/r.height))]}}

function boxAt(i,point){{
  const list=boxes[i];
  for (let k=list.length-1;k>=0;k--) {{
    const box=list[k];
    if (point[0]>=box[0] && point[0]<=box[2] && point[1]>=box[1] && point[1]<=box[3]) return k;
  }}
  return null;
}}

function redraw(i){{
  const canvas=document.querySelector(`canvas[data-index="${{i}}"]`); if(!canvas || !canvas.width)return;
  const context=canvas.getContext('2d');context.clearRect(0,0,canvas.width,canvas.height);
  boxes[i].forEach((box,k)=>{{
    context.strokeStyle = (selected[i]===k) ? '#f6c344' : '#53f28b';
    context.lineWidth=Math.max(2,canvas.width/450);
    context.strokeRect(box[0]*canvas.width,box[1]*canvas.height,(box[2]-box[0])*canvas.width,(box[3]-box[1])*canvas.height);
  }});
}}

function update(i){{
  const frame=frameState(i);frame.boxes=boxes[i].map(box=>({{box,broad_class:'animal',partially_visible:false,
    occluded:false,edge_clipped:false,blurred:false,distance:null,box_confidence:'confident',review_limitation:null}}));
  const section=document.getElementById(`review-${{i}}`);
  section.querySelectorAll('[data-truth]').forEach(button=>button.classList.toggle('selected',button.dataset.truth===frame.whole_frame_truth));
  section.querySelectorAll('.tag-chip').forEach(chip=>chip.classList.toggle('selected',(frame.difficulty_tags||[]).includes(chip.dataset.tag)));
  const noteInput=section.querySelector('.note-input'); if (noteInput && document.activeElement!==noteInput) noteInput.value=frame.reviewer_note||'';
  section.querySelector('.status').textContent=`${{frame.whole_frame_truth}} · ${{boxes[i].length}} human box(es)`;
  redraw(i);
  updateProgress();
}}

function undoBox(i){{boxes[i].pop();delete selected[i];update(i);persist()}}
function clearBoxes(i){{boxes[i]=[];delete selected[i];update(i);persist()}}
function deleteSelectedBox(i){{
  if (selected[i]===undefined || selected[i]===null) {{ if(boxes[i].length) undoBox(i); return; }}
  boxes[i].splice(selected[i],1); delete selected[i]; update(i); persist();
}}

document.querySelectorAll('img.source').forEach(img=>img.addEventListener('load',()=>{{
  const i=Number(img.dataset.index),canvas=document.querySelector(`canvas[data-index="${{i}}"]`);
  const width=Math.min(900,img.naturalWidth);canvas.width=width;canvas.height=Math.round(width*img.naturalHeight/img.naturalWidth);update(i);
}}));
document.querySelectorAll('canvas').forEach(canvas=>{{
  const i=Number(canvas.dataset.index);
  canvas.addEventListener('pointerdown',event=>{{
    const point=normalizedPoint(event,canvas);
    const hit=boxAt(i,point);
    // Landing on a *different*, not-yet-selected box: select it only (no
    // drag starts) -- a second press on that same now-selected box is what
    // starts an edit-drag below. Landing on empty space always clears any
    // stale selection before starting a plain new-box drag, so an edit
    // begun by selecting a box can only ever replace that same box, never
    // whatever was left selected from an earlier, unrelated interaction.
    if (hit!==null && selected[i]!==hit) {{ selected[i]=hit; redraw(i); return; }}
    if (hit===null) delete selected[i];
    starts[i]=point;canvas.setPointerCapture(event.pointerId);
  }});
  canvas.addEventListener('pointerup',event=>{{if(!starts[i])return;const end=normalizedPoint(event,canvas),start=starts[i];delete starts[i];
    const box=[Math.min(start[0],end[0]),Math.min(start[1],end[1]),Math.max(start[0],end[0]),Math.max(start[1],end[1])];
    if(box[2]-box[0]>.003&&box[3]-box[1]>.003){{
      if (selected[i]!==undefined && selected[i]!==null) {{ boxes[i][selected[i]]=box; }} else {{ boxes[i].push(box); }}
      frameState(i).whole_frame_truth='yes';setProvenance(i);update(i);persist();
    }}
  }});
}});

function downloadAnnotations(){{
  const reviewer=document.getElementById('reviewer').value.trim();if(!reviewer){{alert('Enter the reviewer name or initials.');return}}
  for(let i=0;i<annotations.frames.length;i++){{const frame=frameState(i);if(frame.whole_frame_truth==='unreviewed'){{alert(`Frame ${{frame.frame_id}} is unreviewed.`);return}}
    if(frame.whole_frame_truth==='yes'&&!boxes[i].length){{alert(`Animal frame ${{frame.frame_id}} needs a human bounding box.`);return}}setProvenance(i);update(i)}}
  persist();
  const blob=new Blob([JSON.stringify(annotations,null,2)+'\\n'],{{type:'application/json'}}),link=document.createElement('a');
  link.href=URL.createObjectURL(blob);link.download='annotation.json';link.click();URL.revokeObjectURL(link.href);
  document.getElementById('global-status').textContent='Downloaded. Replace this packet\\'s annotation.json, then run temporal-review-validate.';
}}

function handleLoadFile(event){{
  const file=event.target.files && event.target.files[0]; if(!file) return;
  const reader=new FileReader();
  reader.onload=()=>{{
    let parsed;
    try {{ parsed=JSON.parse(reader.result); }} catch(error) {{ alert('That file is not valid JSON: '+error); event.target.value=''; return; }}
    if (parsed.capture_manifest_fingerprint!==annotations.capture_manifest_fingerprint) {{
      alert('That annotation.json was built from a different capture/tranche packet (fingerprint mismatch) and was not loaded.');
      event.target.value=''; return;
    }}
    if (!confirm('Load this file and replace all current in-page progress? This cannot be undone.')) {{ event.target.value=''; return; }}
    applyState(parsed, {{persist:true}});
    document.getElementById('global-status').textContent='Loaded '+file.name+'.';
    event.target.value='';
  }};
  reader.readAsText(file);
}}
const loadFileInput=document.getElementById('load-file');
if (loadFileInput) loadFileInput.addEventListener('change', handleLoadFile);

function updateProgress(){{
  const reviewed=reviewedCount(annotations);
  document.getElementById('progress').textContent=`${{reviewed}} / ${{FRAME_COUNT}} reviewed`;
  const counter=document.getElementById('frame-counter'); if(counter) counter.textContent=`Frame ${{currentIndex+1}} of ${{FRAME_COUNT}}`;
}}

function preload(i){{
  if (i<0 || i>=FRAME_COUNT) return;
  const img=document.querySelector(`img.source[data-index="${{i}}"]`);
  if (img) {{ const warm=new Image(); warm.src=img.getAttribute('src'); }}
}}

function goTo(i){{
  if (FRAME_COUNT===0) return;
  const clamped=Math.max(0,Math.min(FRAME_COUNT-1,i));
  const previous=document.getElementById(`review-${{currentIndex}}`); if(previous) previous.classList.add('hidden');
  currentIndex=clamped;
  const next=document.getElementById(`review-${{currentIndex}}`); if(next) next.classList.remove('hidden');
  try {{ localStorage.setItem(cursorKey(), String(currentIndex)); }} catch(error) {{ /* non-fatal */ }}
  updateProgress();
  preload(currentIndex+1); preload(currentIndex+2);
  if (next) next.scrollIntoView({{block:'start'}});
}}

function jumpToNextUnreviewed(){{
  for (let step=1; step<=FRAME_COUNT; step++) {{
    const candidate=(currentIndex+step)%FRAME_COUNT;
    if (frameState(candidate).whole_frame_truth==='unreviewed') {{ goTo(candidate); return; }}
  }}
  alert('Every frame in this tranche has already been reviewed.');
}}

function toggleSuggestions(){{
  const hidden=document.body.classList.toggle('hide-suggestions');
  document.getElementById('toggle-suggestions-btn').textContent = hidden ? 'Show suggestions' : 'Hide suggestions';
  localStorage.setItem('mockingbird-review-hide-suggestions', hidden ? '1' : '0');
}}

document.addEventListener('keydown', event=>{{
  const target=document.activeElement;
  if (target && (target.tagName==='INPUT' || target.tagName==='TEXTAREA')) return;
  switch (event.key) {{
    case 'a': case 'A': markFrame(currentIndex,'yes'); break;
    case 'n': case 'N': markFrame(currentIndex,'no'); break;
    case 'm': case 'M': markFrame(currentIndex,'ambiguous'); break;
    case 'ArrowRight': case 'j': case 'J': goTo(currentIndex+1); break;
    case 'ArrowLeft': case 'k': case 'K': goTo(currentIndex-1); break;
    case 'Enter': case 's': case 'S': persist(); jumpToNextUnreviewed(); break;
    case 'o': case 'O': toggleSuggestions(); break;
    case 'Delete': case 'Backspace': deleteSelectedBox(currentIndex); event.preventDefault(); break;
    default: return;
  }}
}});

document.getElementById('reviewer').addEventListener('change', event=>{{
  localStorage.setItem('mockingbird-review-reviewer-name', event.target.value.trim());
}});

// Every section is already rendered `hidden` server-side (avoids a flash
// of all frames before this script runs); goTo only ever needs to reveal
// the current one.
loadPersistedState();
goTo(currentIndex);
</script></body></html>"""


def _tranche_context_line(record: dict[str, Any]) -> str:
    """One optional, additive line of Stage-3 tranche/lane/split/priority
    context -- rendered only when the frame record actually carries it, so
    the original single-session reviewer's page is unaffected."""

    lane = record.get("stage3_target_lane")
    if not lane:
        return ""
    tier = escape(str(record.get("priority_tier", "")))
    split = escape(str(record.get("split_candidate", "")))
    return (
        "<p class='tranche-line'>"
        f"tranche={escape(str(record.get('tranche_id', '')))} · lane={escape(str(lane))} · "
        f"priority_tier={tier} · split_candidate={split}</p>"
    )


def _tranche_header_note(frames: list[dict[str, Any]]) -> str:
    tranche_ids = {record.get("tranche_id") for record in frames if record.get("stage3_target_lane")}
    tranche_ids.discard(None)
    if not tranche_ids:
        return ""
    label = escape(", ".join(sorted(str(item) for item in tranche_ids)))
    return f" · tranche {label}"


__all__ = ["render_review_ui"]
