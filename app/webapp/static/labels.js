// Plain-language translations for internal identifiers, so the UI never
// shows a raw config/trigger name to someone who doesn't know the codebase.
const TRIGGER_LABELS = {
  crash_detector: "App crash detected",
  exception_detector: "Unhandled error detected",
  system_detector: "High CPU/memory usage",
  manual_trigger: "Triggered manually",
};

function humanizeTrigger(name) {
  return TRIGGER_LABELS[name] || name;
}

const HOW_IT_WORKS_STEPS = [
  { icon: "eye", title: "Watching", detail: "Screen, system stats, and processes are captured continuously." },
  { icon: "layers", title: "Remembering", detail: "The last ~5 minutes are always kept on hand, just in case." },
  { icon: "alert", title: "Something breaks", detail: "A crash, error, or resource spike fires automatically — or you trigger it yourself." },
  { icon: "lightbulb", title: "AI investigates", detail: "A local AI model reviews everything that just happened." },
  { icon: "fileText", title: "You get an answer", detail: "A plain-English explanation of what went wrong and what to do next." },
];
