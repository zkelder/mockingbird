from datetime import UTC, datetime, timedelta
from mockingbird.motion.effective_primary import EvidenceCandidate, select_effective_primary

NOW = datetime(2026, 1, 1, tzinfo=UTC)
def candidate(id, role, **kw): return EvidenceCandidate(id, role, NOW + kw.pop('offset', timedelta()), **kw)
def test_supported_contained_high_resolution_crop_wins():
    crop=candidate('crop','activity_crop',width=300,height=300,track_box=(.4,.4,.5,.5),crop_box=(.3,.3,.7,.7))
    tracked=candidate('tracked','tracked_best_frame',width=160,height=120)
    assert select_effective_primary([crop,tracked],support_start=NOW,support_end=NOW).reason == 'high_resolution_temporally_aligned'
def test_late_or_clipped_crop_loses_to_tracked_frame():
    crop=candidate('crop','activity_crop',offset=timedelta(seconds=20),width=300,height=300,track_box=(.4,.4,.5,.5),crop_box=(.4,.4,.6,.6))
    tracked=candidate('tracked','tracked_best_frame',width=160,height=120)
    result=select_effective_primary([crop,tracked],support_start=NOW,support_end=NOW)
    assert (result.media_asset_id,result.reason)==('tracked','tracked_best_frame_preferred')
def test_user_choices_win_and_empty_is_honest():
    user=candidate('user','pretrigger',user_selected=True)
    assert select_effective_primary([user]).reason=='user_selected_primary'
    weak=select_effective_primary([candidate('tiny','activity_crop',width=2,height=2)])
    assert (weak.media_asset_id,weak.reason)==('tiny','no_useful_primary_evidence')
