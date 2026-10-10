"""Provedor de IA (opcional). Sem ANTHROPIC_API_KEY o sistema funciona só com regras e heurísticas."""
import json, os, re

class LLMProvider:
    name = "base"
    def complete_json(self, system: str, user: str, max_tokens: int = 2000):
        raise NotImplementedError

def parse_json(text: str):
    t = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    a = min([i for i in (t.find("{"), t.find("[")) if i >= 0], default=-1)
    b = max(t.rfind("}"), t.rfind("]"))
    if a < 0 or b < a: raise ValueError("resposta da IA sem JSON")
    return json.loads(t[a:b + 1])

class AnthropicProvider(LLMProvider):
    name = "anthropic"
    def __init__(self, key: str, model: str):
        import anthropic
        self.client = anthropic.Anthropic(api_key=key, timeout=60); self.model = model
    def complete_json(self, system, user, max_tokens=2000):
        msg = self.client.messages.create(model=self.model, max_tokens=max_tokens, system=system,
                                          messages=[{"role": "user", "content": user}])
        return parse_json("".join(b.text for b in msg.content if getattr(b, "type", "") == "text"))

_forced, _override, _cached = False, None, None

def set_provider(p):          # usado em testes; set_provider(None) simula "sem IA"
    global _forced, _override; _forced, _override = True, p

def reset_provider():
    global _forced, _override; _forced, _override = False, None

def get_llm():
    global _cached
    if _forced: return _override
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key: return None
    if _cached is None:
        try: _cached = AnthropicProvider(key, os.getenv("PDFLOW_AI_MODEL", "claude-sonnet-5-5"))
        except Exception: return None
    return _cached
