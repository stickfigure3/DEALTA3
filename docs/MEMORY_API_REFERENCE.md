# Memory System - API Reference

## Overview
Complete API reference for the DELTA3 Long-Term Memory System, including both AI tool calls and REST API endpoints.

---

## AI Tool Calls (Used by Gemini Agent)

These tools are automatically available to the AI. The AI decides when to call them.

### 1. store_memory

**Purpose**: Save important information to long-term memory

**Parameters**:
```json
{
  "content": "User prefers Python 3.12+",           // Required: What to remember
  "category": "preference",                         // Required: preference|fact|context|skill|project
  "importance": 8,                                  // Required: 1-10 scale
  "tags": ["python", "coding_style"]                // Optional: Searchable tags
}
```

**Response**:
```
✓ Memory stored (ID: 2026-01-28T10:30:45.123Z#a1b2c3d4)
```

**When AI Uses This**:
- User shares preferences ("I prefer X")
- User describes their role/background
- User mentions skills or expertise
- User describes project goals
- Important facts about the user

**Example**:
```
User: "I'm a Python developer who prefers type hints and always uses pytest for testing"
AI: ✓ Memory stored
```

---

### 2. search_memories

**Purpose**: Find relevant memories using keyword search

**Parameters**:
```json
{
  "query": "python",                               // Required: Keyword to search
  "category": "preference",                         // Optional: Filter by category
  "limit": 5                                        // Optional: Max results (default: 5)
}
```

**Response**:
```
Found 2 memories:

- [preference] User prefers Python 3.12+ (Importance: 9, ID: ...)
- [skill] Expert in Python web development (Importance: 8, ID: ...)
```

**When AI Uses This**:
- Before writing code (searches for language preferences)
- When context would be helpful
- To refresh memory about specific topics

---

### 3. list_memories

**Purpose**: List all memories with optional category filter

**Parameters**:
```json
{
  "category": "preference",                        // Optional: Filter by category
  "limit": 20                                      // Optional: Max results (default: 20)
}
```

**Response**:
```
Your memories (5 total):

[PREFERENCE]
  - User prefers Python 3.12+ (Importance: 9, ID: ...)
  - Uses VS Code as main editor (Importance: 7, ID: ...)

[SKILL]
  - Expert in Python web development (Importance: 8, ID: ...)

[CONTEXT]
  - Senior engineer at fintech startup (Importance: 9, ID: ...)
```

**When AI Uses This**:
- User asks "what do you know about me?"
- User asks to list memories
- Reviewing all available context

---

### 4. update_memory

**Purpose**: Update an existing memory when information changes

**Parameters**:
```json
{
  "memory_id": "2026-01-28T10:30:45.123Z#a1b2c3d4",  // Required: Which memory to update
  "new_content": "User prefers Python 3.13 now",      // Required: New content
  "importance": 9                                      // Optional: New importance level
}
```

**Response**:
```
✓ Memory updated
```

**When AI Uses This**:
- User says "Actually, I prefer X now"
- User corrects previous information
- Information becomes more/less important

**Example**:
```
User: "Actually, I switched to TypeScript - I don't use Python much anymore"
AI: ✓ Memory updated
```

---

### 5. delete_memory

**Purpose**: Remove a memory that's no longer relevant

**Parameters**:
```json
{
  "memory_id": "2026-01-28T10:30:45.123Z#a1b2c3d4"  // Required: Which memory to delete
}
```

**Response**:
```
✓ Memory deleted
```

**When AI Uses This**:
- User says "Forget about X"
- User explicitly asks to delete a memory
- Information is no longer relevant

**Example**:
```
User: "Forget my Python preference, I'm moving to Go"
AI: ✓ Memory deleted
(Then might store new: "User is learning Go")
```

---

## REST API Endpoints

These endpoints are called by the frontend UI. Standard HTTP authentication using session token.

### Authentication

All requests require session token header:
```
X-Session-Token: {session_token_from_login}
```

### Content-Type
```
Content-Type: application/json
```

---

### GET /memories

**Purpose**: Retrieve user's memories with optional filtering

**Query Parameters**:
```
?category={category}     // Optional: preference|fact|context|skill|project
&limit={limit}           // Optional: Max results (default: 50)
```

**Example Request**:
```bash
GET /memories?category=preference&limit=20
X-Session-Token: abc123...
```

**Response** (200 OK):
```json
{
  "memories": [
    {
      "user_id": "user@example.com",
      "memory_id": "2026-01-28T10:30:45.123Z#a1b2c3d4",
      "content": "User prefers Python 3.12+",
      "category": "preference",
      "importance": 9,
      "tags": ["python", "coding_style"],
      "created_at": "2026-01-28T10:30:45Z",
      "last_accessed": "2026-01-28T15:22:10Z",
      "access_count": 5
    },
    // ... more memories
  ]
}
```

**Status Codes**:
- `200` - Success
- `400` - Missing/invalid parameters
- `401` - Unauthorized (invalid/missing session token)

---

### DELETE /memories

**Purpose**: Delete a specific memory

**Request Body**:
```json
{
  "memory_id": "2026-01-28T10:30:45.123Z#a1b2c3d4"  // Required
}
```

**Example Request**:
```bash
DELETE /memories
X-Session-Token: abc123...
Content-Type: application/json

{
  "memory_id": "2026-01-28T10:30:45.123Z#a1b2c3d4"
}
```

**Response** (200 OK):
```json
{
  "success": true
}
```

**Status Codes**:
- `200` - Successfully deleted
- `400` - Missing memory_id
- `401` - Unauthorized

---

## Memory Data Model

### DynamoDB Table: `delta3-memories-{environment}`

**Partition Key**: `user_id` (String)
**Sort Key**: `memory_id` (String)

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `user_id` | String | User's email (partition key) |
| `memory_id` | String | Unique ID: `{ISO_TIMESTAMP}#{UUID}` |
| `content` | String | What to remember |
| `category` | String | preference\|fact\|context\|skill\|project |
| `importance` | Number | 1-10 scale (1=minor, 10=critical) |
| `tags` | List | Searchable tags ["tag1", "tag2"] |
| `created_at` | String | ISO timestamp when stored |
| `last_accessed` | String | ISO timestamp last used |
| `access_count` | Number | Times this memory was retrieved |
| `source_context` | String | Optional: why was this stored |

### Global Secondary Indexes

**CategoryIndex**:
- Partition Key: `user_id`
- Sort Key: `category`
- Use: Efficient filtering by category

**ImportanceIndex**:
- Partition Key: `user_id`
- Sort Key: `importance`
- Use: Quick access to high-priority memories

---

## Memory Injection into System Prompt

On each conversation, memories are automatically injected:

### Loading Strategy:
1. All memories with importance >= 9 (critical)
2. All memories from last 7 days with importance >= 6
3. De-duplicated and grouped by category
4. Formatted as context block

### Example Injected Context:
```
=== LONG-TERM MEMORY ===
You have the following information about this user:

[PREFERENCE]
- User prefers Python 3.12+ (Importance: 9)
- Uses VS Code editor (Importance: 7)

[SKILL]
- Expert in Python web development (Importance: 8)

[CONTEXT]
- Senior backend engineer at fintech startup (Importance: 9)

=== END MEMORY ===
```

### Prompt Instructions:
The system prompt includes guidelines:
- When to store memories (preferences, skills, context)
- What NOT to store (transient info, duplicates)
- Importance scoring guidelines
- Category selection guidance

---

## Code Examples

### Python (Lambda Function)

```python
import storage

# Store a memory
result = storage.save_memory(
    user_id="user@example.com",
    content="User prefers Python 3.12 with type hints",
    category="preference",
    importance=8,
    tags=["python", "typing"]
)
# Returns: {"success": True, "memory_id": "..."}

# Search memories
memories = storage.search_memories(
    user_id="user@example.com",
    query="python",
    limit=5
)
# Returns: [memory_dict, memory_dict, ...]

# Get all memories in a category
memories = storage.get_memories(
    user_id="user@example.com",
    category="preference",
    limit=20
)

# Update a memory
result = storage.update_memory(
    user_id="user@example.com",
    memory_id="2026-01-28T10:30:45.123Z#a1b2c3d4",
    new_content="Updated information",
    importance=9
)

# Delete a memory
success = storage.delete_memory(
    user_id="user@example.com",
    memory_id="2026-01-28T10:30:45.123Z#a1b2c3d4"
)
```

### JavaScript (Frontend)

```javascript
// Get memories
const response = await fetch(`${API_URL}/memories?category=preference`, {
    headers: {
        'X-Session-Token': sessionToken,
        'Content-Type': 'application/json'
    }
});
const data = await response.json();
console.log(data.memories);

// Delete a memory
const response = await fetch(`${API_URL}/memories`, {
    method: 'DELETE',
    headers: {
        'X-Session-Token': sessionToken,
        'Content-Type': 'application/json'
    },
    body: JSON.stringify({
        memory_id: "2026-01-28T10:30:45.123Z#a1b2c3d4"
    })
});
const data = await response.json();
console.log(data.success);
```

### cURL Examples

```bash
# Get memories
curl -X GET 'https://api.delta3.com/memories?category=preference' \
  -H 'X-Session-Token: abc123...' \
  -H 'Content-Type: application/json'

# Delete a memory
curl -X DELETE 'https://api.delta3.com/memories' \
  -H 'X-Session-Token: abc123...' \
  -H 'Content-Type: application/json' \
  -d '{"memory_id": "2026-01-28T10:30:45.123Z#a1b2c3d4"}'
```

---

## Rate Limiting

No explicit rate limits currently. DynamoDB on-demand billing handles scaling.

For future reference:
- Single memory: ~1 KB
- Max practical memories: 10,000+ per user
- Query performance: <100ms for most queries
- Scan performance: <500ms for full user memory set

---

## Error Handling

### Common Errors

**401 Unauthorized**:
```json
{
  "error": "Authentication required"
}
```

**400 Bad Request**:
```json
{
  "error": "memory_id required"
}
```

**500 Server Error**:
```json
{
  "error": "DynamoDB error: ..."
}
```

### Retry Logic

Recommended client-side retry strategy:
- Exponential backoff (1s, 2s, 4s)
- Max 3 retries
- Only for 5xx errors, not 4xx

---

## Compliance & Privacy

- Memories are user-specific (stored with user_id)
- No sharing between users
- Can be deleted by user anytime
- Stored in AWS DynamoDB in same region as deployment
- Encrypted at rest (AWS default)

---

## Monitoring & Analytics

### Useful CloudWatch Metrics

```
- Memory store operations: /aws/lambda/delta3-chat-dev
- DynamoDB throttle events: delta3-memories-{env}
- API latency: API Gateway /memories endpoints
- Memory retrieval time: embedded in Lambda logs
```

### Log Examples

```
[INFO] Stored memory: 2026-01-28T10:30:45.123Z#a1b2c3d4
[INFO] Loaded 3 memories for user@example.com in 42ms
[DEBUG] Memory context: 250 chars injected into system prompt
```

---

## Future API Enhancements

Planned for Phase 2+:

- `GET /memories/search` - Advanced search with filters
- `POST /memories/consolidate` - Merge similar memories
- `GET /memories/stats` - Analytics dashboard
- `POST /memories/export` - Export user memories
- `POST /memories/import` - Import memories
- Semantic search with embeddings
- Memory relationships/tags

