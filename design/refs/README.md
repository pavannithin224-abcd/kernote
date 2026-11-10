# Design references

Drop reference material here. This is the input for the UI visual pass.

## What I can read, and what I cannot

| | |
|---|---|
| **PNG / JPG screenshots** | **Yes.** This is the one that works. |
| Text — a name, a URL, a colour, a font | **Yes.** Paste it straight into the chat. |
| Most web pages | **Yes**, I can fetch and read them. |
| **Instagram links** | **No.** Not the video, not the caption, not the comments. |
| Video or screen recordings of any kind | **No.** I cannot watch video. |

Instagram is not merely awkward: the scraper reports the site as unsupported, so
a reel URL yields *nothing at all* — not even the caption that might name the
tool or library being shown.

## Turning a reel into something usable

Two minutes per reel:

1. Play it, and **pause on the frames that matter** — the layout, the palette,
   a chart, a transition's start and end. Three to five frames is plenty.
2. Screenshot each one and save it here.
3. If the reel names a tool, a library, a site, a font or a palette, **paste
   that text into the chat**. A name is worth more than a screenshot: I can go
   and read the source.

## Naming

`NN-topic-what.png`, lowest number first, so the order is the order you want me
to read them in:

```
01-dashboard-layout.png
02-dashboard-charts.png
03-sidebar-collapsed.png
04-motion-transition-start.png
05-motion-transition-end.png
```

For a transition, two frames labelled `-start` and `-end` tell me more than one
frame from the middle.

## A note worth making once

Screenshots of someone else's product are a reference for *craft* — spacing,
hierarchy, restraint, how a chart is labelled, how density is handled. They are
not a specification to reproduce. ADR-0016 already settled this for the
roadmap: other work is reference material, never a template. The same applies
to the interface.
