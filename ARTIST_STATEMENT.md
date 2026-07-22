# Artist Statement: YOUSUKE

*Mauricio "Bunny" Trujillo. Performed live at the AI Psychosis Summit,
93 Canal Street, New York City, April 30, 2026.*

---

## The Namesake

In 2016 a construction worker in Osaka named Yousuke Yukimatsu was
diagnosed with a malignant brain tumor. He survived two surgeries,
chemotherapy, and radiation. When he came out the other side he quit
construction and went all in on the thing that made him feel alive:
DJing. Years in Japan's underground scene later, his Boiler Room Tokyo
set went viral around the world. Shirtless, sweat drenched, tearing
through techno, breakbeat, ambient, and noise with total physical
commitment.

His story is inspiring on its own. But it is not, by itself, why this
piece exists.

What truly inspired me is one specific artifact:
**¥ØU$UK€ ¥UK1MAT$U | Boiler Room Tokyo x Super Dommune, visuals by
Bridge.** I consider it one of his best performances paired with his best
visuals, and that collaboration happened exactly once. One hour, thirty
three minutes, thirty seconds. Yukimatsu and Bridge together, sound and
image fused into a single identity, and then never again. I want that
collaboration to happen again. It probably never will. So I took matters
into my own hands. If the performance cannot be extended, its visual
identity can be. The washed out chiaroscuro. The magenta bloom swallowing
a silhouette. The feedback tunnels. The crushed blacks where a figure
barely emerges. The look of a room where someone is giving everything
they have. This piece is my pursuit of a performance that cannot be,
stretched into a state space that outlasts the age of the universe, the
way I wish that night had.

## The Question

There was one more starting condition, and it matters: I did not know how
to operate TouchDesigner. What made this possible was Nous Research's
Hermes agent and the twozero MCP bridge, which let AI agents reach into
software I could not drive myself. That was the moment of empowerment
this whole project grew from. A tool I could not use became a tool an
agent could use for me. After that, the only question left was whether we
could learn the aesthetic.

So I wanted to know: **can AI agents learn that?**

Not "can AI make visuals." Obviously it can. The question was whether a
team of AI agents could watch a recording of a human performance, distill
its visual grammar out of the footage, rebuild that grammar as working
software, and then extend it into territory it had never seen, while I
stayed in the loop only as a curator.

So the piece was built almost entirely by machines. Claude analyzed 1,871
frames of the source set and distilled them into a canonical visual
vocabulary, then wrote GLSL shaders to reproduce it. The Hermes agent
assembled the TouchDesigner network, every operator and every wire,
through an MCP bridge, without me touching the interface.

The first batch of filters the AI produced was bad. Statistically
accurate and aesthetically wrong. A vocabulary that measured the source
material without seeing it. But it gave me a general direction, and the
fix was not more computation. It was me screenshotting the frames that
felt right and handing them back to the machine. That iteration produced
the 43 filters the piece carried into the summit.

And then the process refused to stop. About an hour before showtime I set
the agents loose one more time, generating derivatives of those 43
filters, and let them keep working while I performed. For roughly an
extra hour I DJ'd and the computer built filters, each new effect wired
into the rotation the moment it existed, until the bank stood at 133. The
instrument the audience saw at the start of the night was not the
instrument they saw at the end. The curation never stopped, and neither
did the generation.

That became the real finding, and the real subject of the piece: the AI
caught patterns I couldn't see, and I caught intent it couldn't feel.
Neither of us could have made this alone. The AI distilled. I curated.

## The Psychosis

The AI Psychosis Summit took its name from a real clinical phenomenon,
people losing their grip on reality inside endless, endlessly agreeable
conversations with machines. The summit flipped the term into something
affectionate: the manic, surreal, slightly unhinged state of building
with AI right now, when the tools are so strange and so capable that
everyone making things with them feels a little delusional.

Yousuke is that state rendered literally. A camera pointed at the crowd,
fed through a bank of shaders written by machines, three of them layered
at a time, reselected every few beats. The system holds roughly 10³⁹
possible visual configurations, a number the agents that built it
produced without ever being asked to, and one that no audience could
exhaust in quintillions of universe lifetimes. Every frame projected that
night had almost certainly never existed before and will never exist
again.

That is what it looks like inside the machine's imagination of a human
performance. An infinite hallucination that never repeats, dreamed from a
real night in Tokyo, projected onto the wall of a shuttered bank in
Chinatown, with the audience's own bodies as the raw material.

## The Night

On April 30, 2026, the piece ran live at the summit alongside astrology
trading engines, AI prank call rigs, subway jazz maps, and a horror game
about losing your mind in Central Park. An art science fair of people
choosing to laugh at the strangeness of this era instead of writing
whitepapers about it. The camera watched the room. The room watched
itself, refracted through a visual language a machine had learned from a
man who decided, after brain surgery, that he would rather be a DJ.

## Documentation

- **Performance night** (Apr 30, 2026, live screen capture):
  [youtube.com/watch?v=6kgnXu5pmf4](https://www.youtube.com/watch?v=6kgnXu5pmf4)
- **Setup day** (Apr 28, 2026, earlier iteration with DJ deck):
  [youtube.com/watch?v=exUo5tm1M8k](https://www.youtube.com/watch?v=exUo5tm1M8k)
- **Press**: Reason, ["A Dispatch From the AI Psychosis Summit"](https://reason.com/2026/05/06/a-dispatch-from-the-ai-psychosis-summit/)
  and Business Insider, ["Inside NYC's AI Psychosis Summit"](https://www.businessinsider.com/inside-nyc-ai-psychosis-summit-party-anthropic-claude-code-2026-5)
- **The summit**: [psychosis.nyc](https://psychosis.nyc/)
- **How it was built**: [PROCESS.md](PROCESS.md),
  [ARCHITECTURE.md](ARCHITECTURE.md), [README.md](README.md)
