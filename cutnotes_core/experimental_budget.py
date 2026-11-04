"""Gemma reasoning cap shared with development experiments; not a semantic proof."""


class ThoughtBudget:
    """State independent of MLX; generated history must exclude prompt tokens."""

    def __init__(self, limit, end_token):
        if not isinstance(limit, int) or limit < 1:
            raise ValueError('Thought budget must be positive')
        self.limit = limit
        self.end_token = end_token
        self.closed = False
        self.closed_at = None
        self.forced = False

    def should_close(self, generated_count, last_generated_token):
        if generated_count and last_generated_token == self.end_token and not self.closed:
            self.closed = True
            self.closed_at = generated_count
        if self.closed:
            return False
        if generated_count >= self.limit:
            self.forced = True
            return True
        return False


def budget_processor(tokenizer, prompt_length, limit, answer_prefix=''):
    """Return a processor and auditable state; keep optional MLX out of imports."""
    import mlx.core as mx
    ids = tokenizer.encode('<channel|>', add_special_tokens=False)
    if len(ids) != 1 or tokenizer.decode(ids) != '<channel|>':
        raise ValueError('Expected a single Gemma channel-end token')
    state = ThoughtBudget(limit, ids[0])
    prefix_ids = tokenizer.encode(answer_prefix,add_special_tokens=False) if answer_prefix else []

    def force(logits, token):
        return mx.where(mx.arange(logits.shape[-1]) == token, 0.0, -float('inf'))[None]

    def process(tokens, logits):
        count = len(tokens) - prompt_length
        last = int(tokens[-1].item()) if count > 0 else None
        if state.should_close(count, last):
            return force(logits,state.end_token)
        if state.closed and count-state.closed_at < len(prefix_ids):
            return force(logits,prefix_ids[count-state.closed_at])
        return logits

    return process, state


def checked_budget_answer(raw, expected_prefix='## Timestamp Notes\n'):
    """Reject malformed channel transitions or a planning preamble after closure."""
    if raw.count('<channel|>') != 1:
        raise ValueError('Expected one thought-to-answer transition')
    answer = raw.split('<channel|>', 1)[1].strip()
    if '<|' in answer or '|>' in answer or not answer.startswith(expected_prefix):
        raise ValueError('Answer channel contains control tokens or an unexpected preamble')
    return answer


def forbidden_special_ids(all_special_ids, eos_ids, allowed_channel_ids=()):
    """Text-only generations still need normal termination and requested channels."""
    return sorted(set(all_special_ids)-set(eos_ids)-set(allowed_channel_ids))


def text_only_bias(tokenizer, thinking):
    allowed = []
    if thinking:
        for token in ['<|channel>','<channel|>']:
            encoded = tokenizer.encode(token,add_special_tokens=False)
            if len(encoded) != 1:
                raise ValueError('Expected a single channel control token')
            allowed.extend(encoded)
    banned = forbidden_special_ids(tokenizer.all_special_ids,tokenizer.eos_token_ids,allowed)
    return {token:-float('inf') for token in banned}
