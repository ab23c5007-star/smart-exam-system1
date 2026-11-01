
from functools import lru_cache
import hashlib
import random
import re

import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM


# ---------------------------------
# AI Model
# ---------------------------------
MODEL_NAME = "google/flan-t5-base"


@lru_cache(maxsize=1)
def get_generator():
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)

    model.eval()

    return tokenizer, model


# ---------------------------------
# Run AI Model
# ---------------------------------
def run_model(prompt):
    tokenizer, model = get_generator()

    inputs = tokenizer(
        prompt,
        return_tensors="pt",
        max_length=512,
        truncation=True
    )

    with torch.inference_mode():
        outputs = model.generate(
            **inputs,
            max_new_tokens=120,
            num_beams=3,
            do_sample=False,
            no_repeat_ngram_size=3
        )

    return tokenizer.decode(
        outputs[0],
        skip_special_tokens=True
    ).strip()


# ---------------------------------
# Clean Text
# ---------------------------------
def clean_text(text):
    return re.sub(
        r"\s+",
        " ",
        text
    ).strip(" \t.,:;-")


# ---------------------------------
# Check Acronym
# ---------------------------------
def acronym_matches(acronym, expansion):
    words = re.findall(
        r"[A-Za-z]+",
        expansion
    )

    if len(words) < 2:
        return False

    initials = "".join(
        word[0].upper()
        for word in words
    )

    return initials == acronym.upper()


# ---------------------------------
# Extract Acronyms from PDF
# ---------------------------------
def extract_acronyms(text):
    pairs = {}

    lines = [
        clean_text(line)
        for line in text.splitlines()
        if clean_text(line)
    ]

    for index, line in enumerate(lines):

        # Example:
        # BSBI stands for Blocked Sort-Based Indexing

        match = re.search(
            r"\b([A-Z]{2,10})\s+stands\s+for\s+"
            r"([A-Za-z][A-Za-z -]{4,100})",
            line
        )

        if match:
            acronym = match.group(1)
            expansion = clean_text(match.group(2))

            if acronym_matches(acronym, expansion):
                pairs[acronym] = expansion

        # Example:
        # BSBI: Blocked Sort-Based Indexing

        match = re.match(
            r"^([A-Z]{2,10})\s*(?:=|:)\s*"
            r"([A-Za-z][A-Za-z -]{4,100})$",
            line
        )

        if match:
            acronym = match.group(1)
            expansion = clean_text(match.group(2))

            if acronym_matches(acronym, expansion):
                pairs[acronym] = expansion

        # Example:
        # Blocked Sort-Based Indexing (BSBI)

        for match in re.finditer(
            r"\(([A-Z]{2,10})\)",
            line
        ):
            acronym = match.group(1)

            before = line[:match.start()]

            words = re.findall(
                r"[A-Za-z]+",
                before
            )

            for count in range(
                2,
                min(len(words), 10) + 1
            ):
                expansion = " ".join(words[-count:])

                if acronym_matches(acronym, expansion):
                    pairs[acronym] = expansion
                    break

        # Example:
        # BSBI
        # Blocked Sort-Based Indexing

        if (
            re.fullmatch(r"[A-Z]{2,10}", line)
            and index + 1 < len(lines)
        ):
            candidate = lines[index + 1]

            if acronym_matches(line, candidate):
                pairs[line] = candidate

    return pairs


# ---------------------------------
# Generate Wrong Options
# ---------------------------------
def generate_wrong_options(
    acronym,
    correct_expansion,
    lecture_text
):
    words = correct_expansion.split()

    if len(words) < 2:
        return []

    replacements = [
        "Distributed",
        "Sequential",
        "Parallel",
        "External",
        "Dynamic",
        "Adaptive",
        "Hierarchical",
        "Centralized",
        "Incremental",
        "Randomized",
        "Recursive",
        "Independent"
    ]

    wrong_options = []

    first_word = re.sub(
        r"[^A-Za-z]",
        "",
        words[0]
    )

    lecture_normalized = clean_text(
        lecture_text
    ).casefold()

    for replacement in replacements:

        if (
            replacement[0].upper()
            == first_word[:1].upper()
        ):
            continue

        candidate_words = words.copy()
        candidate_words[0] = replacement

        candidate = " ".join(candidate_words)

        if (
            candidate.casefold()
            == correct_expansion.casefold()
        ):
            continue

        if candidate.casefold() in lecture_normalized:
            continue

        if acronym_matches(acronym, candidate):
            continue

        if candidate.casefold() not in {
            option.casefold()
            for option in wrong_options
        }:
            wrong_options.append(candidate)

        if len(wrong_options) == 3:
            break

    return wrong_options


# ---------------------------------
# Build One MCQ
# ---------------------------------
def build_mcq(
    acronym,
    expansion,
    lecture_text,
    question_number=1
):
    wrong_options = generate_wrong_options(
        acronym,
        expansion,
        lecture_text
    )

    if len(wrong_options) != 3:
        return None

    options = [expansion] + wrong_options

    seed_text = (
        acronym
        + "|"
        + expansion
        + "|"
        + str(question_number)
    )

    seed = int.from_bytes(
        hashlib.sha256(
            seed_text.encode("utf-8")
        ).digest()[:8],
        "big"
    )

    rng = random.Random(seed)
    rng.shuffle(options)

    answer_index = options.index(expansion)
    correct_letter = "ABCD"[answer_index]

    formatted_options = "\n".join(
        f"{letter}. {option}"
        for letter, option in zip(
            "ABCD",
            options
        )
    )

    return (
        f"Question {question_number}: "
        f"What does {acronym} stand for?\n\n"
        f"{formatted_options}\n\n"
        f"Proposed Correct Answer: "
        f"{correct_letter}. {expansion}\n"
    )


# ---------------------------------
# Generate Multiple MCQs
# ---------------------------------
def generate_multiple_mcqs(text, count=1):

    if count < 1 or count > 20:
        return (
            "Generation failed: "
            "Question count must be between 1 and 20."
        )

    acronyms = extract_acronyms(text)

    if not acronyms:
        return (
            "Generation failed: "
            "No verified acronym expansions "
            "were found in this PDF."
        )

    questions = []

    for acronym, expansion in acronyms.items():

        question = build_mcq(
            acronym,
            expansion,
            text,
            len(questions) + 1
        )

        if question is not None:
            questions.append(question)

        if len(questions) == count:
            break

    generated_count = len(questions)

    if generated_count == 0:
        return (
            "Generation failed: "
            "No complete MCQ could be generated."
        )

    header = (
        f"Requested MCQ Questions: {count}\n"
        f"Generated MCQ Questions: {generated_count}\n\n"
    )

    if generated_count < count:
        header += (
            "Status: PARTIAL RESULT\n"
            "The PDF did not provide enough "
            "verified acronym expansions "
            "for all requested questions.\n\n"
        )
    else:
        header += (
            "Status: DRAFTS GENERATED\n\n"
        )

    result = header + "\n\n".join(questions)

    result += (
        "\n\nAI GENERATED DRAFTS\n"
        "Correct expansions were extracted "
        "from the PDF.\n"
        "Wrong options are programmatically "
        "generated candidate distractors.\n"
        "Teacher must verify all answers "
        "and options."
    )

    return result


# ---------------------------------
# Split Lecture for AI
# ---------------------------------
def split_lecture(text, chunk_size=180):
    words = text.split()

    chunks = []

    for start in range(0, len(words), chunk_size):
        chunk = " ".join(
            words[start:start + chunk_size]
        )

        if len(chunk.split()) >= 25:
            chunks.append(chunk)

    return chunks


# ---------------------------------
# Generate TF or Essay
# ---------------------------------
def generate_ai_questions(
    text,
    question_type,
    count
):

    if count < 1 or count > 20:
        return (
            "Generation failed: "
            "Question count must be between 1 and 20."
        )

    chunks = split_lecture(text)

    if not chunks:
        return (
            "Generation failed: "
            "Not enough lecture text."
        )

    questions = []
    seen = set()

    for chunk in chunks:

        if question_type == "true_false":
            prompt = (
                "Based only on this passage, "
                "write one True or False statement. "
                "Include the answer and explanation.\n\n"
                f"Passage: {chunk}"
            )

        elif question_type == "essay":
            prompt = (
                "Based only on this passage, "
                "write one short essay question "
                "with a model answer.\n\n"
                f"Passage: {chunk}"
            )

        else:
            return (
                "Generation failed: "
                "Invalid question type."
            )

        result = run_model(prompt)

        normalized = clean_text(result).casefold()

        if len(result.split()) < 5:
            continue

        if normalized in seen:
            continue

        seen.add(normalized)

        questions.append(
            f"Question {len(questions) + 1}:\n"
            f"{result}"
        )

        if len(questions) == count:
            break

    if not questions:
        return (
            "Generation failed: "
            "No usable questions were generated."
        )

    return (
        f"Requested Questions: {count}\n"
        f"Generated Questions: {len(questions)}\n\n"
        + "\n\n".join(questions)
        + "\n\nAI GENERATED DRAFTS"
        + "\nTeacher review required."
    )


# ---------------------------------
# Main Generator
# ---------------------------------
def generate_question_from_text(
    text,
    question_type="mcq",
    count=1
):

    if not text or not text.strip():
        return (
            "Generation failed: Empty PDF text."
        )

    if not isinstance(count, int):
        return (
            "Generation failed: Invalid question count."
        )

    if question_type == "mcq":
        return generate_multiple_mcqs(
            text,
            count
        )

    elif question_type in ("true_false", "essay"):
        return generate_ai_questions(
            text,
            question_type,
            count
        )

    else:
        return (
            "Generation failed: Invalid question type."
        )
