import unittest

from contracts.schemas import Candidate, EligibilityRule, ProfileAttributes
from backend.app.agents.eligibility import evaluate
from backend.app.agents.profiling import apply_answer, next_question
from backend.app.agents.scoring import score_scheme
from backend.app.agents.stubs import fixture_profile, fixture_scheme, sample_rules
from backend.app.agents.registry import AgentRegistry
from backend.app.controller.workflow import WorkflowController


class EligibilityTests(unittest.TestCase):
    def test_required_pass_and_manual_becomes_needs_verification(self):
        profile = fixture_profile()
        result = evaluate(profile.attributes, "pmsby", sample_rules()["pmsby"])

        self.assertEqual(result.status, "NEEDS_VERIFICATION")
        self.assertEqual([check.result for check in result.checks], ["pass", "ambiguous"])

    def test_missing_required_field_is_partially_eligible(self):
        result = evaluate(ProfileAttributes(), "demo", [
            EligibilityRule(
                rule_id="r1",
                scheme_id="demo",
                field="age",
                operator="gte",
                value=18,
                kind="required",
                source_text="Applicant must be an adult.",
                citation_id=None,
            )
        ])

        self.assertEqual(result.status, "PARTIALLY_ELIGIBLE")
        self.assertEqual(result.missing_fields, ["age"])


class ScoringTests(unittest.TestCase):
    def test_score_uses_contract_formula(self):
        profile = fixture_profile()
        scheme = fixture_scheme()
        eligibility = evaluate(profile.attributes, scheme.scheme_id, sample_rules()[scheme.scheme_id])
        candidate = Candidate(
            scheme_id=scheme.scheme_id,
            retrieval_score=0.9,
            matched_sectors=[scheme.sector],
            need_similarity=0.5,
        )

        score = score_scheme(profile.attributes, scheme, candidate, eligibility)

        self.assertEqual(score.scheme_id, "pmsby")
        self.assertGreaterEqual(score.match_percent, 0)
        self.assertLessEqual(score.match_percent, 100)
        self.assertEqual(set(score.components), {"profile", "eligibility", "need", "benefit"})


class ProfilingTests(unittest.TestCase):
    def test_next_question_and_apply_answer(self):
        profile = fixture_profile()
        empty = profile.model_copy(update={"attributes": ProfileAttributes(), "complete": False})

        question = next_question(empty)
        self.assertEqual(question.field, "age")

        updated = apply_answer(empty, "age", 30)
        self.assertEqual(updated.version, empty.version + 1)
        self.assertEqual(updated.attributes.age, 30)


class WorkflowTests(unittest.TestCase):
    def test_library_workflow_uses_stubs_without_person_a_integration(self):
        profile = fixture_profile()
        state = WorkflowController(AgentRegistry(use_stubs=True)).library(profile)

        self.assertEqual(state.workflow, "W2")
        self.assertIn("pmsby", state.schemes)
        self.assertIn("pmsby", state.rules)
        self.assertIsNotNone(state.library)
        self.assertEqual(state.library.top[0].scheme_id, "pmsby")


if __name__ == "__main__":
    unittest.main()

