---
name: readme-writing  
description: Write concise, practical project READMEs with only essential information.
---

# README Writing Skill

Create short, clear, consistent README files.

## Structure

Use exactly this order:

1. Banner
2. Application name
3. Description
4. Visual, if available
5. Quickstart

The banner must be the first content, exist in `public/` or `assets/`, contain `banner` in its filename, and use a relative path. Never invent assets.

# Application Name 

--- 

8–13 concise lines describing what the application does and its purpose. Write in English. Avoid repetition, feature lists, marketing language, and technical details. 

---
## See Application Name in action

Picture or video

---
## Quickstart 

### Install 

```bash
npm install # or other command
```

### Run

```bash
npm run dev # or other command
```

Omit the visual section when no relevant screenshot or GIF exists.

## Discovery

Before writing, inspect the project structure, metadata, existing README, and `public/` / `assets/`. Reuse existing assets and commands. Never invent paths, commands, configuration, or content.

## Style

Keep only information needed to understand, install, configure, and run the application. No extra sections, repetition, history, architecture, API documentation, FAQ, or unnecessary badges.

## Validation

Ensure the banner is first, there is exactly one `#` heading, `---` follows the title, the description has 8–13 English lines, visuals are valid when present, and `Quickstart` is the final section.
