# Artist Statement — YOUSUKE

*Mauricio "Bunny" Trujillo — performed live at the AI Psychosis Summit,
93 Canal Street, New York City, April 30, 2026*

---

## The Namesake

In 2016, a construction worker in Osaka named Yousuke Yukimatsu was
diagnosed with a malignant brain tumor. He survived two surgeries,
chemotherapy, and radiation — and when he came out the other side, he quit
construction and went all-in on the thing that made him feel alive: DJing.
Years of Japan's underground scene later, his Boiler Room Tokyo set went
viral around the world — a shirtless, sweat-drenched, genre-annihilating
performance that tears through techno, breakbeat, ambient, and noise with
total physical commitment.

This piece is named after him. Not as appropriation of his music, but as a
study of something harder to name: the *visual identity* of a live moment.
The washed-out chiaroscuro, the magenta bloom swallowing a silhouette, the
feedback tunnels, the crushed blacks out of which a figure barely emerges.
The look of a room where someone is giving everything they have.

## The Question

I wanted to know: **can AI agents learn that?**

Not "can AI make visuals" — obviously it can. The question was whether a
team of AI agents could watch a recording of a human performance, extract
its visual grammar, rebuild that grammar as working software, and then
extend it into new territory it had never seen — while I stayed in the loop
only as a curator.

So the piece was built almost entirely by machines. Claude analyzed 1,871
frames of the source set, clustered them into a canonical visual vocabulary,
and wrote GLSL shaders to reproduce it. The Hermes agent assembled the
TouchDesigner network — every operator, every wire — through an MCP bridge,
without me touching the interface. When the first algorithmic analysis
produced a vocabulary that was statistically accurate but aesthetically
wrong, the fix wasn't more computation. It was me screenshotting the frames
that *felt* right and handing them back to the machine.

That became the real finding, and the real subject of the piece: the AI
caught patterns I couldn't see, and I caught intent it couldn't feel.
Neither of us could have made this alone.

## The Psychosis

The AI Psychosis Summit took its name from a real clinical phenomenon —
people losing their grip on reality inside endless, hyper-agreeable
conversations with machines. The summit flipped the term into something
affectionate: the manic, surreal, slightly unhinged state of building with
AI in this moment, when the tools are so strange and so capable that
everyone making things with them feels a little delusional.

Yousuke is that state rendered literally. A camera pointed at the crowd,
fed through a bank of machine-written shaders, three of them layered at a
time, re-selected every few beats. The system occupies a state space of
roughly 10³⁹ possible visual configurations — a number the AI agents that
built it produced without ever being asked to, and one that no audience
could exhaust in quintillions of universe lifetimes. Every frame projected
that night had almost certainly never existed before and will never exist
again.

That is what it looks like inside the machine's imagination of a human
performance: an infinite, non-repeating hallucination of a real night in
Tokyo, projected onto a wall of a shuttered bank in Chinatown, with the
audience's own bodies as the raw material.

## The Night

On April 30, 2026, the piece ran live at the summit alongside astrology
trading engines, AI prank-call rigs, subway-jazz maps, and a horror game
about losing your mind in Central Park — an art-science-fair of people
choosing to laugh at the strangeness of this era instead of writing
whitepapers about it. The camera watched the room; the room watched itself,
refracted through a visual language a machine had learned from a man who
decided, after brain surgery, that he would rather be a DJ.

## Documentation

- **Performance night** (Apr 30, 2026, live screen capture):
  [youtube.com/watch?v=6kgnXu5pmf4](https://www.youtube.com/watch?v=6kgnXu5pmf4)
- **Setup day** (Apr 28, 2026, earlier iteration with DJ deck):
  [youtube.com/watch?v=exUo5tm1M8k](https://www.youtube.com/watch?v=exUo5tm1M8k)
- **Press** — Reason, ["A Dispatch From the AI Psychosis Summit"](https://reason.com/2026/05/06/a-dispatch-from-the-ai-psychosis-summit/)
  · Business Insider, ["Inside NYC's AI Psychosis Summit"](https://www.businessinsider.com/inside-nyc-ai-psychosis-summit-party-anthropic-claude-code-2026-5)
- **The summit**: [psychosis.nyc](https://psychosis.nyc/)
- **How it was built**: [PROCESS.md](PROCESS.md) ·
  [ARCHITECTURE.md](ARCHITECTURE.md) · [README.md](README.md)
