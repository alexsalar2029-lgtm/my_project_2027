"""Bounded model-output parsing and diagnostics; never retain raw provider replies."""
import json
import re

LANGS = ('fa', 'en', 'ar', 'es')


class ModelOutputError(ValueError):
    def __init__(self, code):
        # Codes are constructed locally, never from provider error text or source content.
        self.code = code
        super().__init__(code)


def parse_output(raw, truncated=False):
    if truncated:
        raise ModelOutputError('model_output_truncated')
    if not isinstance(raw, str) or not raw.strip():
        raise ModelOutputError('model_output_empty')
    text = raw.strip().lstrip('\ufeff').strip()
    fenced = re.fullmatch(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', text, re.I)
    if fenced:
        text = fenced[1].strip()
    try:
        result = json.loads(text)
    except (json.JSONDecodeError, RecursionError):
        raise ModelOutputError('model_json_invalid') from None
    if not isinstance(result, dict):
        raise ModelOutputError('model_object_required')
    return result


def output_schema():
    """Constrain local generation to a compact, complete four-language document."""
    def translated(limit):
        return {'type':'object', 'properties':{
            lang:{'type':'string','minLength':1,'maxLength':limit} for lang in LANGS},
            'required':list(LANGS), 'additionalProperties':False}
    return {'type':'object', 'properties':{
        'kind':{'type':'string','enum':['sale','tutorial','article']},
        'brand':{'type':'string','enum':['generic','nordvpn','crunchyroll','dazn',
                                       'netflix','spotify','youtube','surfshark']},
        'title':translated(180), 'summary':translated(350), 'body':translated(1200),
        'price':{'anyOf':[{'type':'null'},{'type':'object', 'properties':{
            'amount':{'type':'string'}, 'currency':{'type':'string','enum':['USDT','USD','EUR']}},
            'required':['amount','currency'],'additionalProperties':False}]}},
        'required':['kind','brand','title','summary','body','price'], 'additionalProperties':False}


def correction_instructions(problem):
    """Return fixed instructions; do not put untrusted exception strings in a prompt."""
    code = problem.code
    field = re.fullmatch(r'model_(title|summary|body)(?:_(fa|en|ar|es))?_(object|missing|empty|not_text|too_long|generic)', code)
    if field:
        target = field[1] + ('.'+field[2] if field[2] else '')
        instruction = 'Correct the '+target+' field; the validation issue is '+field[3]+'.'
    else:
        instruction = {
            'model_output_truncated':'Your previous response ran out of output space. Make all four versions more concise.',
            'model_output_empty':'Your previous response had no JSON content.',
            'model_json_invalid':'Your previous response was not valid JSON. Escape quotes and newlines correctly.',
            'model_object_required':'Return one JSON object, not an array or string.',
            'model_classification_invalid':'Use exactly sale, tutorial or article as kind.',
        }.get(code, 'Correct the response to match the required JSON structure.')
    return ('Regenerate the complete result from the original untrusted source. '+instruction+
            ' Include nonempty fa, en, ar and es strings in title, summary and body. '
            'Use product-specific single-line titles, a summary of at most 350 characters and '
            'a body of at most 1200 characters per language. Do not invent missing facts. '
            'Return only the JSON object; do not add explanations.')
