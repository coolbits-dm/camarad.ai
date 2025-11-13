# M18 — Custom Agents & Prompt Editor

**Status**: 🔴 Not Started  
**Priority**: P1 (Important)  
**Estimated Effort**: 5-7 days  
**Dependencies**: M4 (Agents), M12 (AI Runtime)

## Goal

Allow users to create custom agents with personalized roles, instructions, and tool configurations.

## Database Schema Changes

```sql
ALTER TABLE agents ADD COLUMN is_custom BOOLEAN DEFAULT FALSE;
ALTER TABLE agents ADD COLUMN base_preset_id VARCHAR(50);
ALTER TABLE agents ADD COLUMN custom_instructions TEXT;
ALTER TABLE agents ADD COLUMN enabled_tools JSONB DEFAULT '[]';

-- Example tools: ["web_search", "calculator", "code_interpreter", "image_generation"]
```

## UI Flow

1. User clicks "Create Custom Agent"
2. Select base template (optional) OR start from scratch
3. Configure:
   - Name
   - Icon
   - Role prompt (with guidance/examples)
   - Enabled tools (checkboxes)
   - Model selection (GPT-4, Claude, etc.)
4. Preview agent behavior
5. Save → Creates agent with `is_custom=true`

## Prompt Editor

```typescript
interface PromptTemplate {
  role: string;
  instructions: string;
  constraints: string[];
  examples: Array<{ input: string; output: string }>;
}
```

## API Endpoints

- `POST /api/agents/custom` - Create custom agent
- `PATCH /api/agents/:id/prompt` - Update agent prompt
- `GET /api/agents/templates` - List prompt templates

## Key Features

- Rich text prompt editor with syntax highlighting
- Prompt templates (e.g., "Customer Support Bot", "Code Reviewer")
- Tool selection (web search, calculator, code execution)
- Model selection (GPT-4, Claude 3, etc.)
- Preview mode (test agent before saving)
- Prompt validation (character limits, safety checks)
- Version history (rollback to previous prompts)

## Testing

- [ ] Custom agents created successfully
- [ ] Prompts saved correctly
- [ ] Tools enabled/disabled work
- [ ] Preview mode functional
- [ ] Version history works
- [ ] Custom agents limited by plan
