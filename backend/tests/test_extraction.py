"""The deterministic gate between LLM output and the database (no LLM, no DB)."""
from ingestion.extract_facts import CitedText, ExtractedRule, Extraction, MaxBenefit, rule_problem, verify

CHUNKS = {"aaaaaaaaaaaaaaaa-p1-c0": "Subscribers aged 18 to 40 years can join. Pension of Rs 3,000 per month after 60.",
          "aaaaaaaaaaaaaaaa-p2-c0": "Income tax payers are excluded from the scheme."}


def rule(**kw):
    base = dict(field="age", operator="between", value=[18, 40], kind="required",
                source_text="aged 18 to 40 years", citation_ids=["aaaaaaaaaaaaaaaa-p1-c0"], confidence=0.9)
    return ExtractedRule(**{**base, **kw})


def test_valid_rules_pass():
    assert rule_problem(rule()) is None
    assert rule_problem(rule(field="social_category", operator="in", value=["sc", "st"])) is None
    assert rule_problem(rule(field="is_bpl", operator="is_true", value=None)) is None
    assert rule_problem(rule(field="_unmapped", operator="manual", value=None)) is None


def test_invalid_rules_are_caught():
    assert rule_problem(rule(field="caste", operator="eq", value="sc"))                     # not a profile field
    assert rule_problem(rule(field="social_category", operator="in", value=["sc", "dalit"]))  # value not allowed
    assert rule_problem(rule(operator="between", value=[40, 18]))                          # reversed range
    assert rule_problem(rule(field="gender", operator="lte", value=5))                      # number op on choice
    assert rule_problem(rule(field="_unmapped", operator="eq", value=True))                 # unmapped must be manual


def test_uncited_items_are_dropped_and_invalid_rules_become_manual():
    ex = Extraction(
        benefits=[CitedText(text="Pension of Rs 3,000 per month after 60", citation_ids=["aaaaaaaaaaaaaaaa-p1-c0"]),
                  CitedText(text="Free laptop", citation_ids=["bbbbbbbbbbbbbbbb-p9-c9"])],     # not shown to model
        rules=[rule(), rule(field="occupation", operator="eq", value="tax_payer", kind="exclusion",
                            source_text="Income tax payers are excluded", citation_ids=["aaaaaaaaaaaaaaaa-p2-c0"])])
    stored, notes = verify(ex, CHUNKS)
    assert [f["text"] for f in stored["facts"]] == ["Pension of Rs 3,000 per month after 60"]
    assert stored["rules"][0]["operator"] == "between" and stored["rules"][0]["review_status"] == "unreviewed"
    r2 = stored["rules"][1]
    assert (r2["field"], r2["operator"], r2["value"], r2["review_status"]) == ("_unmapped", "manual", None, "flagged")
    assert any("dropped benefit" in n for n in notes)


def test_weakly_supported_fact_is_flagged_not_trusted():
    ex = Extraction(benefits=[CitedText(text="Free tractor and house for every member",
                                        citation_ids=["aaaaaaaaaaaaaaaa-p1-c0"])])
    stored, _ = verify(ex, CHUNKS)
    assert stored["facts"][0]["review_status"] == "flagged"


def test_max_benefit_amount_must_appear_in_the_cited_text():
    ok, _ = verify(Extraction(max_benefit=MaxBenefit(amount_inr=3000, period="per_month",
                                                     citation_ids=["aaaaaaaaaaaaaaaa-p1-c0"])), CHUNKS)
    bad, notes = verify(Extraction(max_benefit=MaxBenefit(amount_inr=5000, period="per_month",
                                                          citation_ids=["aaaaaaaaaaaaaaaa-p1-c0"])), CHUNKS)
    assert ok["max_benefit"].amount_inr == 3000 and bad["max_benefit"] is None and notes


def test_indian_amounts_and_word_forms_are_understood():
    from ingestion.extract_facts import amounts, support_ratio
    assert {200000, 2} <= amounts("Sum Insured = Rs. 2 Lakh") | {2}
    assert 200000 in amounts("Rs 2,00,000") and 15000000 in amounts("1.5 crore")
    assert support_ratio("Cover terminates at age 70", ["Termination of cover: on attaining age 70"]) >= 0.5
    chunks = {"aaaaaaaaaaaaaaaa-p1-c0": "Sum Insured = Rs. 2 Lakh for accidental death."}
    stored, _ = verify(Extraction(max_benefit=MaxBenefit(amount_inr=200000, period="one_time",
                                                         citation_ids=["aaaaaaaaaaaaaaaa-p1-c0"])), chunks)
    assert stored["max_benefit"].amount_inr == 200000


def test_wrong_neighbour_citation_is_corrected_to_the_chunk_that_contains_the_quote():
    r = rule(field="age", operator="between", value=[18, 70], source_text="aged between 18 years and 70 years",
             citation_ids=["aaaaaaaaaaaaaaaa-p2-c0"])
    chunks = {"aaaaaaaaaaaaaaaa-p1-c0": "Applicants aged between 18 years and 70 years can join.",
              "aaaaaaaaaaaaaaaa-p2-c0": "Income tax payers are excluded from the scheme."}
    stored, notes = verify(Extraction(rules=[r]), chunks)
    assert stored["rules"][0]["citation_id"] == "aaaaaaaaaaaaaaaa-p1-c0"
    assert stored["rules"][0]["review_status"] == "unreviewed" and any("recited" in n for n in notes)
