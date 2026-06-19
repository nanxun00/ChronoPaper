# doc-forge

A Claude Code Skill — Full-pipeline toolkit for turning conversations into professional software engineering deliverables.

## What is this

doc-forge bridges the gap between non-technical stakeholders and development teams. It guides anyone — including bosses and product managers with zero coding knowledge — through a friendly conversation, then automatically generates requirement documents, architecture diagrams, and promotional visuals.

**Core philosophy:**
- Let clients participate in requirement definition through guided conversation
- Turn ambiguous ideas into structured, professional documents
- Auto-generate diagrams and visuals from confirmed requirements
- Cover the full software development lifecycle (SDLC)

**Who is it for:**
- **Non-technical stakeholders (甲方)** — Describe your idea in plain language. Claude asks questions like "What problem does this solve?" and "Who will use it?", then turns your answers into professional documents automatically
- **Developers (乙方)** — Use it as a structured tool to collect, organize, and deliver client requirements
- **Teams** — Collaborate in real-time during meetings, generating documents and diagrams on the spot

## Features

### Intelligent Requirement Gathering

- **Role-Based Conversation** — Choose your role (client / developer / collaborator) and the tool adapts its language and questions accordingly
- **Free-Form Input** — Describe your project however you like: plain text, keywords, a reference product, or even a screenshot
- **Smart Follow-Up Questions** — AI analyzes your description and generates numbered follow-up questions, with priority markers and batch answer support
- **Conflict Detection** — Automatically detects contradictions in your requirements (e.g., "feature-rich" vs "minimal UI") and helps you resolve trade-offs

### Document Generation

- **Section-by-Section Refinement** — Generate a chapter outline first, then refine each section through an interactive loop with brainstorming, drafting, and confirmation
- **Dual-Perspective Verification** — Optionally validate the document from both a client readability perspective and a developer feasibility perspective
- **Self-Check & Polish** — Automatic review for terminology consistency, vague expressions, and missing acceptance criteria
- **Word Export** — Convert any generated Markdown document to `.docx` format, with all PlantUML diagrams embedded as inline images at their corresponding positions

### Diagram Generation

- **4 Diagram Types** — Data Flow Diagram (DFD), Use Case Diagram, Activity Diagram, Sequence Diagram
- **Multiple Formats** — PNG (web), SVG (presentations), PDF (print)
- **PlantUML Powered** — Source code preserved alongside rendered images

### Visual Assets

- **Banner Images** — Project branding with tagline and visual style
- **Feature Showcase** — Card-style illustrations of core features
- **UI Wireframes** — Minimal annotated wireframe mockups
- **Multi-Model Support** — Choose from gpt-image-1, dall-e-3, or dall-e-2

### Project Management

- **Unified Output Directory** — All deliverables (documents, diagrams, images) organized in a single project folder
- **Timestamped Versions** — Each run creates timestamped artifacts for traceability
- **Incremental Updates** — Re-run to update specific modules without regenerating everything

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/ljy-negroni/doc-forge.git
cd doc-forge

# 2. Install dependencies
npm install

# 3. Configure environment
cp .env.example .env
# Edit .env and fill in your OPENAI_API_KEY

# 4. Register as Claude Code command
cp skill/SKILL.md ~/.claude/commands/doc-forge.md

# 5. Run in Claude Code
/doc-forge
```

## Typical Workflow

```
1. Choose your role: client, developer, or collaborator
2. Describe your project freely — in any format you like
3. Answer follow-up questions — skip what you're unsure about
4. Resolve any detected conflicts in your requirements
5. Review the document section by section — confirm or modify each part
6. Optionally verify from client and developer perspectives
7. Auto-generate architecture diagrams (DFD, Use Case, Activity, Sequence)
8. Auto-generate promotional images and UI wireframes
9. Export the final document to Word (.docx) with diagrams embedded inline
10. All deliverables saved in one folder, ready to share
```

## Project Structure

```
doc-forge/
├── skill/SKILL.md              # Skill definition (conversation flow + tool invocation)
├── scripts/
│   ├── plantuml-render.js      # PlantUML encoding + rendering (PNG/SVG/PDF)
│   ├── image-generate.js       # Multi-model image generation
│   └── md-to-word.js           # Markdown → Word (.docx) with embedded diagram images
├── templates/
│   ├── doc-template.md         # Document section structure template
│   └── plantuml-prompts.md     # PlantUML generation prompt templates
├── .env.example                # Environment variable template
└── package.json
```

## Status

Core pipeline is fully functional.

- [x] Role-based conversation (client / developer / collaborator)
- [x] Free-form project description with smart follow-up questions
- [x] Conflict detection and trade-off resolution
- [x] Section-by-section document refinement
- [x] Dual-perspective document verification
- [x] PlantUML diagram rendering (PNG / SVG / PDF)
- [x] Multi-model image generation (gpt-image-1 / dall-e-3 / dall-e-2)
- [x] Unified output directory with timestamped versions
- [x] Incremental update support
- [ ] Word export — Markdown to .docx with PlantUML diagrams embedded inline
- [ ] SDLC Mode — problem definition & feasibility analysis for non-technical users
- [ ] Database schema design (interactive field definition + SQL export)
- [ ] PPT report generation
- [ ] ER diagram support
- [ ] Multi-language document output (Chinese / English)
