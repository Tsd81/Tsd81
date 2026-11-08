# Blender Skills (внесени)

- **Източник:** https://github.com/arjun988/blender-skills
- **Commit:** `904f095d8f36a6e72adaebb08d07f884a074743d` (06.11.2026), версия 1.3.0
- **Лиценз:** MIT, виж `LICENSE-blender-skills`
- **Съдържание:** 94 skills + споделени `references/` (само .md файлове, без скриптове)

## Как работят
Claude Code зарежда автоматично всяка папка с `SKILL.md` от `.claude/skills/` на проекта.
Входна точка за сложни задачи: `blender-director` (маршрутизира към останалите).
Пълен списък и дървета за избор: `SKILLS_GUIDE.md`.

## Изпълнение в Blender
Skills са инструкции. За реално изпълнение в Blender е нужен Blender MCP
(`uvx blender-mcp`) и стартиран Blender с добавката BlenderMCP на `localhost:9876`.
`.mcp.json` от оригинала не е копиран: той е за Windows (`cmd /c`) и не работи в облачна сесия.

## Обновяване
```bash
git clone --depth 1 https://github.com/arjun988/blender-skills.git /tmp/bs
rsync -a --delete --exclude 'README-blender-skills.md' --exclude 'LICENSE-blender-skills' \
  --exclude 'SKILLS_GUIDE.md' /tmp/bs/.claude/skills/ .claude/skills/
```
Внимание: `--delete` ще изтрие и други skills в `.claude/skills/`, ако добавите такива.
