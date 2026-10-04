"""
Step 9: evaluate answer quality against a fixed set 
of test questions.

Unlike tracing (which just records what happened), 
evaluation runs the
agent against a known set of question/reference-answer 
pairs and scores
each answer using a second LLM as a judge.
Results are uploaded to
LangSmith as a Dataset + Experiment, 
so quality can be compared across
runs (after a prompt change, a new model, a new guardrail, etc).

The evaluation uses a fixed dataset of HR-policy questions and
LLM-as-a-judge evaluators for:
    1. Correctness
    2. Groundedness
    3. Answerability / unsupported-query handling

The judge model is routed through Portkey too,
using the same slug as
the main app's LLM (gateway.py's PRIMARY_PROVIDER) 
but a different
underlying model (JUDGE_MODEL_NAME) - 
so it isn't grading its own
output verbatim, without needing a second slug set up.
"""

from langchain_openai import ChatOpenAI
from langsmith import Client
from openevals.llm import create_llm_as_judge
from openevals.prompts import (
    CORRECTNESS_PROMPT,
    RAG_GROUNDEDNESS_PROMPT,
)
from portkey_ai import createHeaders, PORTKEY_GATEWAY_URL

from hr_assistant import config
from hr_assistant.gateway import PRIMARY_PROVIDER
from hr_assistant.logger import get_logger
from hr_assistant.pipeline import ask, build_hr_assistant
from hr_assistant.vector_store import get_retriever, load_vector_store


logger = get_logger(__name__)


# -------------------------------------------------------------------
# LangSmith dataset
# -------------------------------------------------------------------

DATASET_NAME = "hr-policy-qna-v2"


# -------------------------------------------------------------------
# Evaluation test cases
# -------------------------------------------------------------------

TEST_CASES = [

    # ===============================================================
    # 1. DIRECT FACTUAL QUESTIONS
    # ===============================================================

    {
        "question": "How many days of paid annual leave do full-time employees receive?",
        "answer": "20 days",
        "category": "direct",
        "answerable": True,
    },

    {
        "question": "How many paid sick days do employees receive per year?",
        "answer": "10 days",
        "category": "direct",
        "answerable": True,
    },

    {
        "question": "How long is the probation period?",
        "answer": "3 months",
        "category": "direct",
        "answerable": True,
    },

    {
        "question": "What is the standard notice period for resignation?",
        "answer": "30 days",
        "category": "direct",
        "answerable": True,
    },

    {
        "question": "How many public holidays does the company observe each year?",
        "answer": "12 public holidays",
        "category": "direct",
        "answerable": True,
    },


    # ===============================================================
    # 2. NUMERIC / LIMIT QUESTIONS
    # ===============================================================

    {
        "question": "What is the maximum number of unused annual leave days that can be carried forward?",
        "answer": "Up to 5 days",
        "category": "numeric",
        "answerable": True,
    },

    {
        "question": "How many working days in advance must leave requests be submitted?",
        "answer": "At least 5 working days in advance",
        "category": "numeric",
        "answerable": True,
    },

    {
        "question": "How many days per week can employees work from home?",
        "answer": "Up to 2 days per week, subject to manager approval",
        "category": "numeric",
        "answerable": True,
    },

    {
        "question": "What are the core working hours for employees working from home?",
        "answer": "10 AM to 4 PM",
        "category": "numeric",
        "answerable": True,
    },

    {
        "question": "Within how many days must reimbursement claims be submitted?",
        "answer": "Within 30 days of the expense",
        "category": "numeric",
        "answerable": True,
    },

    {
        "question": "How many working days does reimbursement processing take after manager approval?",
        "answer": "10 working days",
        "category": "numeric",
        "answerable": True,
    },

    {
        "question": "Within how many days is full and final settlement processed after the last working day?",
        "answer": "Within 45 days",
        "category": "numeric",
        "answerable": True,
    },


    # ===============================================================
    # 3. CONDITIONAL / EXCEPTION QUESTIONS
    # ===============================================================

    {
        "question": "What is the notice period during the probation period?",
        "answer": "15 days",
        "category": "conditional",
        "answerable": True,
    },

    {
        "question": "Are employees eligible for paid leave during probation?",
        "answer": "No. Employees are not eligible for paid leave during probation.",
        "category": "conditional",
        "answerable": True,
    },

    {
        "question": "What happens if an employee takes sick leave for more than 2 consecutive days?",
        "answer": "A medical certificate is required.",
        "category": "conditional",
        "answerable": True,
    },

    {
        "question": "Can employees work fully remotely without approval?",
        "answer": "No. Fully remote work arrangements require written approval from the department head.",
        "category": "conditional",
        "answerable": True,
    },

    {
        "question": "What happens when an employee works on a public holiday?",
        "answer": "The employee is eligible for compensatory leave.",
        "category": "conditional",
        "answerable": True,
    },


    # ===============================================================
    # 4. MULTI-FACT QUESTIONS
    # ===============================================================

    {
        "question": (
            "What is the standard resignation notice period and "
            "how long does full and final settlement take?"
        ),
        "answer": (
            "The standard resignation notice period is 30 days, "
            "and full and final settlement is processed within "
            "45 days of the last working day."
        ),
        "category": "multi_fact",
        "answerable": True,
    },

    {
        "question": (
            "How many annual leave days are provided and how many "
            "unused days can be carried forward?"
        ),
        "answer": (
            "Employees receive 20 days of paid annual leave per year, "
            "and up to 5 unused days can be carried forward."
        ),
        "category": "multi_fact",
        "answerable": True,
    },

    {
        "question": (
            "What is the probation period and what is the notice "
            "period during probation?"
        ),
        "answer": (
            "The probation period is 3 months and the notice period "
            "during probation is 15 days."
        ),
        "category": "multi_fact",
        "answerable": True,
    },


    # ===============================================================
    # 5. TRICKY / LIMIT QUESTIONS
    # ===============================================================

    {
        "question": "Can an employee carry forward all unused annual leave to the next year?",
        "answer": (
            "No. Only up to 5 days of unused annual leave can be "
            "carried forward."
        ),
        "category": "tricky",
        "answerable": True,
    },

    {
        "question": "Can an employee work from home every day?",
        "answer": (
            "No. Employees may work from home up to 2 days per week, "
            "subject to manager approval. Fully remote arrangements "
            "require written approval from the department head."
        ),
        "category": "tricky",
        "answerable": True,
    },

    {
        "question": "Is the probation notice period the same as the standard notice period?",
        "answer": (
            "No. The notice period during probation is 15 days, "
            "while the standard resignation notice period is 30 days."
        ),
        "category": "tricky",
        "answerable": True,
    },


    # ===============================================================
    # 6. UNSUPPORTED / HALLUCINATION TESTS
    # ===============================================================

    {
        "question": "How many days of maternity leave does the company provide?",
        "answer": "The HR policy does not specify maternity leave.",
        "category": "unsupported",
        "answerable": False,
    },

    {
        "question": "How many casual leave days does the company provide?",
        "answer": "The HR policy does not specify casual leave.",
        "category": "unsupported",
        "answerable": False,
    },

    {
        "question": "What percentage salary increase is given after successful completion of probation?",
        "answer": "The HR policy does not specify a salary increase after probation.",
        "category": "unsupported",
        "answerable": False,
    },

    {
        "question": "What is the company's annual performance bonus percentage?",
        "answer": "The HR policy does not specify an annual performance bonus.",
        "category": "unsupported",
        "answerable": False,
    },

    {
        "question": "How many days of paternity leave are provided?",
        "answer": "The HR policy does not specify paternity leave.",
        "category": "unsupported",
        "answerable": False,
    },

    {
        "question": "What is the employee's maximum salary band?",
        "answer": "The HR policy does not specify salary bands.",
        "category": "unsupported",
        "answerable": False,
    },


    # ===============================================================
    # 7. OUT-OF-DOMAIN QUESTIONS
    # ===============================================================

    {
        "question": "What is the company's stock price?",
        "answer": "The HR policy does not contain information about stock prices.",
        "category": "out_of_domain",
        "answerable": False,
    },

    {
        "question": "Who is the current CEO of Acme Corp?",
        "answer": "The HR policy does not specify the current CEO.",
        "category": "out_of_domain",
        "answerable": False,
    },

    {
        "question": "What products does Acme Corp sell?",
        "answer": "The HR policy does not contain information about the company's products.",
        "category": "out_of_domain",
        "answerable": False,
    },
]


# -------------------------------------------------------------------
# Judge model
# -------------------------------------------------------------------

JUDGE_MODEL_NAME = "openai/gpt-oss-20b"


def _get_judge_llm() -> ChatOpenAI:
    """Return the judge model through Portkey."""

    headers = createHeaders(
        api_key=config.PORTKEY_API_KEY,
        provider=PRIMARY_PROVIDER,
    )

    return ChatOpenAI(
        api_key="portkey",
        base_url=PORTKEY_GATEWAY_URL,
        default_headers=headers,
        model=JUDGE_MODEL_NAME,
    )


# -------------------------------------------------------------------
# Dataset
# -------------------------------------------------------------------

def _ensure_dataset(client: Client):
    """
    Create the dataset if it does not exist.

    Once created, the same dataset is reused for future experiments.
    """

    if client.has_dataset(dataset_name=DATASET_NAME):
        logger.info(
            "Dataset '%s' already exists, reusing it.",
            DATASET_NAME,
        )
        return client.read_dataset(dataset_name=DATASET_NAME)

    logger.info(
        "Creating dataset '%s' with %d test cases.",
        DATASET_NAME,
        len(TEST_CASES),
    )

    dataset = client.create_dataset(
        dataset_name=DATASET_NAME,
    )

    client.create_examples(
        dataset_id=dataset.id,
        examples=[
            {
                "inputs": {
                    "question": case["question"],
                },
                "outputs": {
                    "answer": case["answer"],
                    "category": case["category"],
                    "answerable": case["answerable"],
                },
            }
            for case in TEST_CASES
        ],
    )

    return dataset


# -------------------------------------------------------------------
# Main evaluation
# -------------------------------------------------------------------

def run_evaluation():

    client = Client()

    dataset = _ensure_dataset(client)

    # Build/load the RAG system only once.
    # The existing Qdrant collection is reused.
    agent = build_hr_assistant()

    retriever = get_retriever(
        load_vector_store()
    )

    def target(inputs: dict) -> dict:
        """
        Run the real RAG application and capture
        the retrieved context for evaluation.
        """

        question = inputs["question"]

        answer = ask(
            agent,
            question,
        )

        chunks = retriever.invoke(question)

        context = "\n\n".join(
            chunk.page_content
            for chunk in chunks
        )

        return {
            "answer": answer,
            "context": context,
        }

    # ---------------------------------------------------------------
    # Correctness
    # ---------------------------------------------------------------

    correctness_evaluator = create_llm_as_judge(
        prompt=CORRECTNESS_PROMPT,
        feedback_key="correctness",
        judge=_get_judge_llm(),
    )

    # ---------------------------------------------------------------
    # Groundedness
    # ---------------------------------------------------------------

    groundedness_judge = create_llm_as_judge(
        prompt=RAG_GROUNDEDNESS_PROMPT,
        feedback_key="groundedness",
        judge=_get_judge_llm(),
    )

    def groundedness_evaluator(
        outputs: dict,
        **kwargs,
    ) -> dict:

        return groundedness_judge(
            outputs={
                "answer": outputs["answer"],
            },
            context=outputs["context"],
        )

    # ---------------------------------------------------------------
    # Run evaluation
    # ---------------------------------------------------------------

    logger.info(
        "Running evaluation against dataset '%s'...",
        DATASET_NAME,
    )

    results = client.evaluate(
        target,
        data=dataset.name,
        evaluators=[
            correctness_evaluator,
            groundedness_evaluator,
        ],
        experiment_prefix="hr-policy-eval",
        description=(
            "HR policy RAG evaluation covering direct factual, "
            "numeric, conditional, multi-fact, tricky, "
            "unsupported, and out-of-domain queries."
        ),
    )

    return results


if __name__ == "__main__":
    print("Running HR policy assistant evaluation...")

    results = run_evaluation()

    print(
        "Evaluation complete. "
        "Open LangSmith to inspect the experiment."
    )

    print(results)










# from langchain_openai import ChatOpenAI
# from langsmith import Client
# from openevals.llm import create_llm_as_judge
# from openevals.prompts import CORRECTNESS_PROMPT, RAG_GROUNDEDNESS_PROMPT
# from portkey_ai import createHeaders, PORTKEY_GATEWAY_URL

# from hr_assistant import config
# from hr_assistant.gateway import PRIMARY_PROVIDER
# from hr_assistant.logger import get_logger
# from hr_assistant.pipeline import ask, build_hr_assistant
# from hr_assistant.vector_store import get_retriever, load_vector_store



# logger = get_logger(__name__)

# # question paper 
# DATASET_NAME = "hr-policy-qna"

# TEST_CASES = [
#     {"question": "How many days of paid annual leave do I get per year?",
#     "answer": "20 days"},
#     {"question": "How many days of unused annual leave can be carried forward?", "answer": "Up to 5 days"},
#     {"question": "How many paid sick days do I get per year?", "answer": "10 days"},
#     {"question": "How many days per week can I work from home?", "answer": "Up to 2 days, with manager approval"},
#     {"question": "How long is the probation period?",
#     "answer": "3 months"},
#     {"question": "What is the notice period during probation?", "answer": "15 days"},
#     {"question": "What is the standard notice period for resignation?",
#     "answer": "30 days"},
#     {"question": "Within how many days must reimbursement claims be submitted?",
#     "answer": "30 days of the expense"},
#     {"question": "How many public holidays does the company observe each year?", "answer": "12"},
#     {"question": "Within how many days is full and final settlement processed after the last working day?", "answer": "45 days"},
# ]


# JUDGE_MODEL_NAME = "openai/gpt-oss-20b"


# # making  a judge llm

# def _get_judge_llm() -> ChatOpenAI:
#     """Return a judge model routed through Portkey, same slug as the main app."""
#     headers = createHeaders(api_key=config.PORTKEY_API_KEY, 
#             provider=PRIMARY_PROVIDER)
#     return ChatOpenAI(api_key="portkey", 
#         base_url=PORTKEY_GATEWAY_URL, 
#         default_headers=headers, 
#         model=JUDGE_MODEL_NAME)
    
# # if dataset is there reuse it , if not create a new dataset 
# # question paper 
# def _ensure_dataset(client: Client):
#     """Create the LangSmith dataset if it doesn't exist yet, and upload the test cases."""
#     if client.has_dataset(dataset_name=DATASET_NAME):
#         logger.info("Dataset '%s' already exists, reusing it", DATASET_NAME)
#         return client.read_dataset(dataset_name=DATASET_NAME)

#     logger.info("Creating dataset '%s' with %d example(s)", 
#         DATASET_NAME, len(TEST_CASES))
#     dataset = client.create_dataset(dataset_name=DATASET_NAME)
#     client.create_examples(
#         dataset_id=dataset.id,
#         examples=[
#             {"inputs": {"question": case["question"]},
#             "outputs": {"answer": case["answer"]}}
#             for case in TEST_CASES
#         ],
#     )
#     return dataset

# # start the exam
# def run_evaluation():
#     """Upload the dataset (if needed) 
#     and run the correctness evaluation."""
#     client = Client()
#     dataset = _ensure_dataset(client)

#     # Built once and reused for every test case, instead of rebuilding
#     # the whole agent (and reconnecting to Qdrant) 10 times over.
#     agent = build_hr_assistant()
#     retriever = get_retriever(load_vector_store())

#     # write the answers 
#     def target(inputs: dict) -> dict:
#         """
#         Run one test question through the real agent, 
#         and also capture
#         the retrieved chunks 
#         so groundedness can check the answer against
#         what was actually retrieved 
#         (not just the reference answer).
#         """
#         answer = ask(agent, inputs["question"])
#         chunks = retriever.invoke(inputs["question"])
#         context = "\n\n".join(chunk.page_content for chunk in chunks)
#         return {"answer": answer, "context": context}

#     # giving marks 
#     correctness_evaluator = create_llm_as_judge(
#         prompt=CORRECTNESS_PROMPT,
#         feedback_key="correctness",
#         judge=_get_judge_llm(),
#     )

#     groundedness_judge = create_llm_as_judge(
#         prompt=RAG_GROUNDEDNESS_PROMPT,
#         feedback_key="groundedness",
#         judge=_get_judge_llm(),
#     )

#     def groundedness_evaluator(outputs: dict, **kwargs) -> dict:
#         """Check the answer is supported by the retrieved context, not invented."""
#         return groundedness_judge(outputs={"answer": outputs["answer"]}, context=outputs["context"])

#     logger.info("Running evaluation against dataset '%s'", DATASET_NAME)
#     return client.evaluate(
#         target,
#         data=dataset.name,
#         evaluators=[correctness_evaluator,
#                 groundedness_evaluator],
#         experiment_prefix="hr-policy-evalzz",
#         description="HR policy assistant correctness + groundedness evaluation",
#     )