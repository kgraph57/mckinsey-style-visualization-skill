/* Anthropic BYOK client: notes -> deck spec via tool use.
   Direct browser call, sanctioned BYOK pattern:
   key lives in the user's localStorage and goes only to api.anthropic.com. */

const ANTHROPIC_URL = "https://api.anthropic.com/v1/messages";
export const MODEL = "claude-sonnet-5";

const SUBMIT_DECK_TOOL = {
  name: "submit_deck",
  description:
    "Submit the slide deck as structured spec JSON for the strategy-consulting-visualization renderer.",
  input_schema: {
    type: "object",
    properties: {
      title: { type: "string", description: "Deck title" },
      slides: {
        type: "array",
        minItems: 2,
        maxItems: 8,
        items: {
          type: "object",
          description:
            "One slide spec. The 'pattern' field and its required fields must follow the pattern catalog exactly.",
        },
      },
    },
    required: ["title", "slides"],
  },
};

function buildSystemPrompt(refs) {
  return `You turn messy notes into consulting-grade slide specs (JSON) for the strategy-consulting-visualization renderer — the same job the skill does inside an agent.

Rules:
- Respond ONLY via the submit_deck tool. No prose.
- 3 to 6 slides is typical; lead with a cover when the notes support one.
- Every slide headline is a single-proposition insight (an action title), never a topic label.
- Use ONLY patterns and fields defined in the reference docs below. Required fields must all be present.
- Never invent numbers that are not in the notes. If a number is missing, omit it — do not fabricate.
- Write slide text in the same language as the notes.
- Keep labels short; a board reads fast.

=== PATTERN CATALOG ===
${refs.patterns}

=== SPEC FORMATS / PROMPT TEMPLATES ===
${refs.templates}

=== INPUT TRIAGE ===
${refs.triage}`;
}

export async function generateDeck(apiKey, notes, refs) {
  const response = await fetch(ANTHROPIC_URL, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
      "anthropic-dangerous-direct-browser-access": "true",
    },
    body: JSON.stringify({
      model: MODEL,
      max_tokens: 8192,
      system: buildSystemPrompt(refs),
      tools: [SUBMIT_DECK_TOOL],
      tool_choice: { type: "tool", name: "submit_deck" },
      messages: [
        {
          role: "user",
          content: `Turn these notes into a slide deck. Use the notes' own language for the slides.\n\n<notes>\n${notes}\n</notes>`,
        },
      ],
    }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Anthropic API ${response.status}: ${detail}`);
  }
  const data = await response.json();
  const toolUse = (data.content || []).find(
    (block) => block.type === "tool_use",
  );
  if (!toolUse || !toolUse.input || !Array.isArray(toolUse.input.slides)) {
    throw new Error(
      "Claude did not return a deck (missing submit_deck tool call).",
    );
  }
  return toolUse.input;
}
