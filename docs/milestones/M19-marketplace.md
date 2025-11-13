# M19 — Marketplace Prep (Agent Templates)

**Status**: 🔴 Not Started  
**Priority**: P2 (Future)  
**Estimated Effort**: 7-10 days  
**Dependencies**: M18 (Custom Agents)

## Goal

Enable users to publish and share custom agent templates in a public marketplace.

## Database Schema

```sql
CREATE TABLE agent_templates (
  id UUID PRIMARY KEY,
  created_by UUID NOT NULL REFERENCES users(id),
  name VARCHAR(255) NOT NULL,
  description TEXT,
  category VARCHAR(50), -- 'business', 'personal', 'developer', 'creative'
  icon VARCHAR(50),
  prompt TEXT NOT NULL,
  enabled_tools JSONB DEFAULT '[]',
  is_published BOOLEAN DEFAULT FALSE,
  downloads_count INT DEFAULT 0,
  rating DECIMAL(2,1),
  reviews_count INT DEFAULT 0,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE template_reviews (
  id UUID PRIMARY KEY,
  template_id UUID NOT NULL REFERENCES agent_templates(id),
  user_id UUID NOT NULL REFERENCES users(id),
  rating INT NOT NULL CHECK (rating BETWEEN 1 AND 5),
  review TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_templates_category ON agent_templates(category, downloads_count DESC);
CREATE INDEX idx_templates_rating ON agent_templates(rating DESC, downloads_count DESC);
```

## Marketplace Features

- Browse templates by category
- Search templates by keywords
- Sort by popularity, rating, newest
- Preview template details before adding
- One-click "Add to Workspace" button
- Template reviews and ratings
- Creator profiles with published templates

## API Endpoints

- `GET /api/marketplace/templates` - Browse marketplace
- `GET /api/marketplace/templates/:id` - Template details
- `POST /api/marketplace/templates/:id/install` - Add to workspace
- `POST /api/agents/:id/publish` - Publish custom agent
- `POST /api/templates/:id/review` - Submit review

## Moderation

- Manual approval for first-time publishers
- Content filtering (no harmful prompts)
- Report abuse functionality
- Takedown process for violations

## Testing

- [ ] Templates published successfully
- [ ] Marketplace browsing works
- [ ] Search and filters functional
- [ ] Install templates works
- [ ] Reviews/ratings display
- [ ] Moderation queue functional
