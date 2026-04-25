(() => {
  const es = new EventSource("/ops/events");
  es.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === "rebuilt") {
      console.log("[forge-overlay] Rebuild detected, reloading...");
      location.reload();
    }
  };
  es.onerror = () => {
    console.warn("[forge-overlay] SSE connection lost, will retry...");
  };
})();
