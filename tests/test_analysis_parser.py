from app.webapp.analysis_parser import parse_analysis

SAMPLE = """\
## Most Likely Cause
The hog process segfaulted after consuming 97% CPU.

## Supporting Evidence
- t=-2.0: crash report for hog
- t=-1.0: process terminated

## Alternative Explanations
None considered plausible.

## Suggested Next Steps
- Inspect the hog binary for memory issues
- Check for a recent update to hog
"""


def test_parses_all_four_sections():
    sections = parse_analysis(SAMPLE)

    assert "segfaulted" in sections.most_likely_cause
    assert len(sections.supporting_evidence) == 2
    assert sections.alternative_explanations == "None considered plausible."
    assert len(sections.next_steps) == 2
    assert sections.next_steps[0] == "Inspect the hog binary for memory issues"


def test_falls_back_to_most_likely_cause_when_unstructured():
    sections = parse_analysis("The model just wrote free text with no headings.")

    assert sections.most_likely_cause == "The model just wrote free text with no headings."
    assert sections.supporting_evidence == []


def test_handles_empty_text():
    sections = parse_analysis("")
    assert sections.most_likely_cause == ""
    assert sections.next_steps == []
