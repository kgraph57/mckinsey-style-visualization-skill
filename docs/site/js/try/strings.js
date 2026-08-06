/* Shared lang-aware UI strings for the try/console surfaces. */

const IS_JA = document.documentElement.lang === "ja";

export const STR = {
  needKey: IS_JA
    ? "先にAPIキーを保存してください。"
    : "Save your API key first.",
  needNotes: IS_JA ? "メモを入力してください。" : "Paste some notes first.",
  stRefs: IS_JA
    ? "レンダラーのルールブックを読み込み中…"
    : "Reading the renderer's rulebook…",
  stClaude: IS_JA
    ? "Claudeにメモを渡しています…"
    : "Handing your notes to Claude…",
  stRenderer: IS_JA
    ? "レンダラーを起動しています（初回のみ約12MB）…"
    : "Starting the renderer (first time only, ~12 MB)…",
  stDraw: IS_JA ? "スライドを描画しています…" : "Drawing slides…",
  stDone: IS_JA ? "できました。" : "Done.",
  copied: IS_JA ? "コピーしました" : "Copied",
  sampleNotes: IS_JA
    ? "ARRは$10Mから$15Mに成長した。エンタープライズ新規が+$3M、既存顧客の拡大が+$2.5M、チャーンが-$0.5M。AIワークフローの導入率は18%から64%に上昇。取締役会で実装キャパシティへの投資判断が必要。"
    : "ARR grew from $10M to $15M. Enterprise added $3M, expansion $2.5M, churn -$0.5M. AI workflow adoption grew from 18% to 64%. The board must decide on implementation capacity investment.",
};
