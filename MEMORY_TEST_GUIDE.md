# Long-Term Memory System - Testing Guide

## Quick Start

After deployment, follow these steps to test the memory system:

## Test 1: Basic Memory Storage

### What to test:
1. Start a new chat conversation
2. Send message: "Remember that I prefer Python 3.12 and always want type hints"
3. Watch the AI response
4. Check if the AI calls `store_memory` tool (should see ✓ Memory stored in response)

### Expected behavior:
- AI recognizes preference and stores it
- Success message with memory ID returned
- Memory saved to DynamoDB with:
  - category: "preference"
  - importance: 8-10
  - tags: ["python", "type_hints"]

---

## Test 2: Memory Context Injection

### What to test:
1. In same conversation, ask: "Write a simple Python script"
2. In a NEW conversation/browser session, ask: "Write a Python script"
3. Compare the code written in both scenarios

### Expected behavior:
- First conversation: Generic Python code
- Second conversation: Code uses Python 3.12+ features and includes type hints
- AI should use stored preferences without being asked again

---

## Test 3: Viewing Memories in UI

### What to test:
1. Click the memory icon (clipboard icon) in top right
2. Memories panel should slide in from right
3. Should show stored memories grouped by category
4. Each memory card should show:
   - Content
   - Category (in header)
   - Importance level (colored badge: red=9-10, orange=7-8, blue=5-6, gray=1-4)
   - Date created
   - Tags (if any)
   - Access count
   - Delete button

### Expected behavior:
- All stored memories visible
- Grouped logically by category
- Color-coded by importance
- Delete button functional

---

## Test 4: Memory Filtering

### What to test:
1. With memories panel open, try each filter button:
   - All (shows all memories)
   - Preferences
   - Facts
   - Context
   - Skills
   - Projects
2. Filter buttons should update list

### Expected behavior:
- Each filter button highlights when active
- Memory list updates to show only that category
- "All" shows everything
- Empty categories show: "No memories yet..."

---

## Test 5: Memory Deletion

### What to test:
1. Open memories panel
2. Click "Delete" button on any memory
3. Confirm deletion in popup
4. Memory should disappear from list

### Expected behavior:
- Delete button triggers confirmation dialog
- Memory removed from DynamoDB
- List refreshes automatically
- Deleted memory no longer used in subsequent conversations

---

## Test 6: Multiple Memory Types

### What to test:
Send the AI these different types of information in one conversation:

```
1. "I work as a senior backend engineer at a fintech startup" (context)
2. "I'm expert in Go and Rust programming" (skill)
3. "I prefer using PostgreSQL over MongoDB" (preference)
4. "Our current project involves building a trading engine" (project)
5. "The capital markets never sleep - we need 24/7 uptime" (fact)
```

### Expected behavior:
- AI stores 4-5 memories (may consolidate related items)
- Each memory has appropriate category
- Importance varies based on relevance (project/context=high, preferences=medium)
- Next conversation, AI remembers all this context

---

## Test 7: Search in New Conversation

### What to test:
1. Store several memories in Conversation 1
2. Start Conversation 2
3. Ask: "What do you know about my preferences?"
4. AI calls `list_memories` and responds with stored preferences

### Expected behavior:
- AI correctly identifies and lists preferences
- Response acknowledges category filters
- No need for user to repeat information

---

## Test 8: Memory Updates

### What to test:
1. Store: "I prefer Python 3.10"
2. Later, send: "Actually, I use Python 3.13 now"
3. AI recognizes this is an update and calls `update_memory` or stores new one

### Expected behavior:
- Memory updated or new memory stored with higher importance
- AI acknowledges the update
- Next conversation uses updated information

---

## Test 9: Performance with Many Memories

### What to test:
1. Store 20+ memories across conversations
2. Start a new conversation
3. Check response time

### Expected behavior:
- Initial context loading (first API call) takes <500ms
- Memory context properly injected
- No degradation in AI response speed
- All memories properly indexed and queryable

---

## Test 10: Mobile Responsiveness

### What to test:
1. Open on mobile/tablet
2. Click memories button
3. Panel should open full-width
4. All filtering and deletion should work

### Expected behavior:
- Panel slides in full width on mobile
- All buttons and text readable
- Delete confirmation works
- Can scroll through long memory lists

---

## Debugging Tips

### Check DynamoDB:
```bash
aws dynamodb scan --table-name delta3-memories-dev --region us-east-1
```

### Check Lambda Logs:
```bash
aws logs tail /aws/lambda/delta3-chat-dev --follow
```

### Frontend Console:
Open browser DevTools (F12) and check:
- Console for errors
- Network tab for API calls to `/memories`
- Application/Storage to view localStorage (session token)

### Common Issues:

**Q: Memories panel shows "No memories found" but conversation shows they're stored**
- A: Check browser console for API errors
- Try refreshing the page
- Verify MEMORIES_TABLE environment variable is set

**Q: AI not using stored memories in new conversations**
- A: Memories might have importance < 6 (increase threshold in code)
- Check AI's system_instruction includes memory context
- Verify `_load_memories()` is being called

**Q: Delete button not working**
- A: Check browser console for errors
- Verify session token is still valid
- Try with a different memory

**Q: Memory importance not color-coded correctly**
- A: Check CSS classes match importance level (importance-1 to importance-10)
- Verify frontend JavaScript rounds importance correctly: `Math.round(mem.importance)`

---

## Performance Baseline

Record these metrics to track system health:

- [ ] Time to load memories on first open: ____ms
- [ ] Time to store new memory: ____ms
- [ ] Time to delete memory: ____ms
- [ ] Number of memories before performance degrades: _____
- [ ] Average API response time with 50 memories: ____ms

## Success Criteria

✅ All tests pass when:
- Memories store successfully
- Context injection works automatically
- UI displays all memories correctly
- Filtering works as expected
- Deletion works reliably
- Performance is acceptable
- Mobile experience is smooth
- No console errors
- All API calls return 200/204

Once all tests pass, the implementation is ready for production use!
