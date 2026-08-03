# Interview Canvas

So I want to create an application that would would be front end for this and I already want to start thinking about creating the back end so right now for the back end I want you to just mock the calls to back end and then later I will implement back end myself.  # System Design Interview Platform




## Product and Technical Specification — MVP v1.0




**Status:** Draft  

**Date:** August 3, 2026  

**Audience:** Product, design, engineering, QA, and security  




## 1. Product summary




The product is a browser-based collaborative workspace for conducting live system-design interviews. An interviewer creates an interview session and shares a unique link. One or more candidates and interviewers can join the session and work together on the same infinite canvas in real time.




Participants can place common architecture components, move and resize them, connect them with arrows, add labels and notes, and draw freehand. Every authorized participant sees updates immediately. The system preserves the final canvas and a record of the session for later interviewer review.




## 2. Goals




The MVP must:




1. Let an interviewer create and manage an interview session.

2. Generate a secure, shareable candidate link.

3. Allow multiple participants to join from modern desktop browsers.

4. Provide a low-latency, real-time shared canvas.

5. Support structured system-design diagrams and freehand drawing.

6. Recover gracefully from brief network interruptions.

7. Save the interview canvas automatically for later review.

8. Clearly identify participants and show who is currently active.




## 3. Non-goals for MVP




The following are intentionally excluded from the first release:




- Built-in video or audio calls

- Automated candidate scoring or hiring recommendations

- AI-generated interview answers or architecture suggestions during a session

- A full applicant-tracking system integration

- Code execution or collaborative coding

- Native mobile applications

- Offline-first editing

- Public template marketplace

- Playback of every historical canvas operation




These can be considered after the core interviewing workflow is reliable.




## 4. Users and roles




### 4.1 Interviewer




An authenticated user who can:




- Create, start, end, and reopen an interview session

- Configure session title, prompt, duration, and access settings

- Copy or revoke the candidate link

- Join and edit the canvas

- View participant presence

- Lock or unlock candidate editing

- View saved sessions and final canvases

- Duplicate a previous session as a reusable template




### 4.2 Candidate




A guest or authenticated user who joins through a valid session link and can:




- Enter a display name before joining

- Read the interview prompt

- Edit the canvas while the session allows candidate editing

- See other participants and their cursors

- Reconnect to the same session after a temporary disconnect




A candidate cannot create sessions, change session configuration, access other interviews, or reopen an ended session unless explicitly permitted.




### 4.3 Additional interviewer or observer




An authenticated person invited by the owner. In the MVP, an additional interviewer may edit the canvas. An observer may view the session but cannot edit. Only the session owner can revoke links, change roles, or end the interview.




## 5. Core user flows




### 5.1 Create and share an interview




1. The interviewer signs in and selects **New interview**.

2. The interviewer enters a title and optional problem statement.

3. The system creates a draft session and a blank canvas.

4. The interviewer optionally pre-populates the canvas or selects a template.

5. The interviewer selects **Create candidate link**.

6. The system generates a high-entropy, revocable link.

7. The interviewer copies and sends the link to the candidate.




### 5.2 Join an interview




1. The candidate opens the link.

2. The system validates that the token is active and the session is joinable.

3. The candidate enters a display name and accepts a short privacy notice.

4. The candidate joins the canvas.

5. Existing participants see the candidate appear in the participant list.

6. The candidate receives the current canvas state, then live updates.




### 5.3 Conduct the interview




1. Participants place components, draw, add text, and connect elements.

2. Each participant sees remote cursors, selections, and edits in real time.

3. Changes save automatically.

4. If a participant disconnects, local edits are queued and synchronized after reconnection when safe.

5. The interviewer may temporarily lock candidate editing without removing the candidate.




### 5.4 End and review




1. The owner selects **End interview** and confirms.

2. The session becomes read-only for candidates.

3. The system saves a final snapshot.

4. The interviewer can reopen the result from the interview dashboard.

5. The interviewer can export the canvas as PNG or PDF in a post-MVP increment; JSON export is recommended in the MVP for support and portability.




## 6. Functional requirements




### 6.1 Authentication and session management




- Interviewers must authenticate using email magic link or an organizational identity provider.

- Candidates may join as guests using the candidate link.

- Every session has one owner, a lifecycle state, creation and update timestamps, and an associated canvas.

- Session states are `draft`, `live`, `ended`, and `archived`.

- The owner can rotate or revoke the candidate link at any time.

- A link may optionally have an expiration time and maximum participant count.

- Default maximum: 10 concurrent participants per session.

- The system must reject joins to revoked, expired, archived, or capacity-limited sessions with a clear message.




### 6.2 Interview lobby




The join page must show:




- Product name and session title

- Candidate display-name field

- Basic browser compatibility warning when needed

- Microcopy explaining that canvas activity is saved

- Join button and meaningful errors




The interview prompt must not be exposed until the interviewer-configured access condition is met. For the MVP, the default is to expose it immediately after joining.




### 6.3 Shared canvas




The canvas must support:




- Infinite pan and zoom

- Mouse, trackpad, and basic stylus input

- Multi-select using drag selection and modifier keys

- Move, resize, duplicate, delete, group, ungroup, and layer ordering

- Undo and redo scoped to the current participant's actions where technically feasible

- Copy and paste within the canvas

- Keyboard deletion and common shortcuts

- Snap-to-grid and alignment guides

- Zoom-to-fit and reset view

- Visible selection outlines labeled with the participant's name or color




Canvas viewport position is personal and is not synchronized. Canvas content is synchronized.




### 6.4 Component palette




The MVP palette must include:




| Category | Components |

| --- | --- |

| General | Service/process rectangle, rounded rectangle, text, sticky note, boundary/group, generic icon |

| Data | Relational database, NoSQL database, cache, object/file storage, data warehouse |

| Messaging | Queue, event stream/topic, pub/sub broker |

| Network | Client, browser/mobile client, API gateway, load balancer, CDN, external API |

| Compute | Server, worker, function/serverless, container/cluster |

| AI | LLM/model, embedding model, vector database, agent/tool |




Each component must have:




- A stable component type

- Default icon or shape and label

- Editable text label

- Optional description

- Connection points

- Resizable dimensions with sensible minimums

- Accessible color contrast




Users can also create an untyped rectangle or ellipse and label it freely.




### 6.5 Connections




- Participants can create directed or undirected connectors between elements.

- Connector styles: straight, elbow, and curved.

- Arrowheads can be enabled at either or both ends.

- Connectors remain attached when elements move.

- A connector may have a label, such as `HTTPS`, `events`, or `read/write`.

- Connectors can be selected, restyled, redirected, and deleted.

- Optional MVP styles: solid and dashed lines, adjustable color, and three line widths.




### 6.6 Freehand and annotation tools




- Pen tool with selectable color and width

- Eraser that removes an entire stroke on contact

- Highlighter with transparency

- Freehand strokes represented as vector paths, not raster images

- Text tool for standalone labels

- Sticky notes with editable text and background color

- Optional laser pointer that is ephemeral and not persisted




### 6.7 Real-time collaboration




- All committed canvas operations must propagate to connected participants.

- Target propagation latency: p95 below 250 ms within the same deployment region, excluding the user's network.

- Presence information includes display name, assigned color, connection state, cursor location, and selected objects.

- Cursor and viewport-presence events are ephemeral and need not be stored.

- Persistent changes must have deterministic conflict handling using a CRDT or an equivalent operation-based collaboration model.

- The system must tolerate out-of-order and duplicate messages.

- A newly joined participant receives a consistent snapshot followed by operations occurring after that snapshot.

- After reconnecting, a participant must converge to the authoritative canvas state without reloading the page.




### 6.8 Autosave and recovery




- Persistent canvas operations are durably stored at least every 2 seconds during active editing.

- The server creates periodic compact snapshots to avoid replaying an unbounded operation log.

- Reloading the page restores the latest confirmed state.

- A connection-status indicator must distinguish connected, reconnecting, and offline states.

- If synchronization cannot safely merge an offline change, the product must preserve the authoritative canvas and inform the user; it must not silently discard server data.




### 6.9 Session controls




The owner can:




- Start and end the session

- Lock or unlock candidate editing

- Remove a participant

- Rotate or revoke the guest link

- Toggle cursor visibility

- Clear the canvas after confirmation while preserving a recoverable prior snapshot




All participants can see whether editing is enabled and whether the session has ended.




### 6.10 Dashboard




The interviewer dashboard lists owned sessions with:




- Title

- State

- Creation date

- Scheduled or actual session time, if provided

- Participant names

- Last modified time

- Actions: open, copy link, duplicate, archive




Search, filters, teams, and organization-level administration are post-MVP unless needed for the initial customer.




## 7. UX layout




Recommended desktop layout:




- **Top bar:** session title, connection state, participants, timer, share, and end-session controls

- **Left toolbar:** select, hand/pan, pen, highlighter, eraser, text, sticky note, connector, and component library

- **Center:** infinite canvas

- **Right panel:** selected-element properties; collapsible interview prompt when nothing is selected

- **Bottom controls:** zoom, zoom-to-fit, undo, and redo




The interface should maximize canvas area. Destructive controls require confirmation and must be visually separated from routine editing controls.




## 8. Accessibility and compatibility




- Target WCAG 2.2 AA for non-canvas UI.

- All toolbar controls must have names, tooltips, and visible keyboard focus.

- Core diagram objects must be selectable, movable, relabeled, connected, and deleted using a keyboard.

- Color cannot be the sole indicator of participant or object state.

- Support the latest two major versions of Chrome, Edge, Firefox, and Safari on desktop.

- Tablet browsers may be best-effort in the MVP; phone editing is not supported.




## 9. Permissions matrix




| Capability | Owner | Interviewer | Candidate | Observer |

| --- | ---: | ---: | ---: | ---: |

| View canvas while session is accessible | Yes | Yes | Yes | Yes |

| Edit canvas while unlocked | Yes | Yes | Yes | No |

| Invite participant | Yes | Optional | No | No |

| Lock candidate editing | Yes | Optional | No | No |

| Remove participant | Yes | No | No | No |

| End session | Yes | No | No | No |

| Revoke candidate link | Yes | No | No | No |

| View ended session | Yes | Yes, if invited | No by default | If invited |

| Archive or delete session | Yes | No | No | No |




## 10. Recommended architecture




### 10.1 Client




- TypeScript single-page web application

- Canvas rendering layer using an established diagramming library or a custom SVG/canvas hybrid

- Local collaboration document for optimistic editing

- WebSocket connection for persistent operations and presence

- HTTPS REST or RPC calls for session and account management




An established canvas library should be evaluated before building low-level selection, transforms, connectors, and text editing. The collaboration document should remain independent enough that the renderer can be replaced.




### 10.2 Backend services




1. **Web/API service:** authentication, sessions, participants, links, permissions, and dashboard APIs.

2. **Collaboration gateway:** WebSocket connections, room membership, validation, operation fan-out, presence, and rate limiting.

3. **Persistence worker:** batches operation writes and generates snapshots.

4. **Export worker:** creates image/PDF exports when that feature is enabled.




### 10.3 Storage




- Relational database for users, sessions, memberships, invite tokens, and audit events

- Durable object/blob storage for canvas snapshots and exports

- Durable operation store, either relational or a log-oriented database

- In-memory data store for ephemeral room presence, connection routing, and pub/sub across collaboration gateway instances




### 10.4 Horizontal scaling




- Web/API instances are stateless.

- WebSocket instances share room events through pub/sub or use room-affine routing.

- Persistent operation sequence or CRDT update identifiers prevent duplicate application.

- Snapshot compaction runs asynchronously and never blocks live editing.




## 11. Data model




### User




- `id`

- `email`

- `display_name`

- `organization_id` (nullable)

- `created_at`




### InterviewSession




- `id`

- `owner_user_id`

- `title`

- `prompt`

- `state`

- `candidate_editing_enabled`

- `scheduled_at` (nullable)

- `started_at` (nullable)

- `ended_at` (nullable)

- `created_at`

- `updated_at`




### SessionMembership




- `session_id`

- `user_id` or `guest_participant_id`

- `role`

- `created_at`




### GuestLink




- `id`

- `session_id`

- `token_hash`

- `role_granted`

- `expires_at` (nullable)

- `max_uses` (nullable)

- `revoked_at` (nullable)

- `created_at`




Only a cryptographic hash of the bearer token is stored.




### Participant




- `id`

- `session_id`

- `user_id` (nullable)

- `display_name`

- `role`

- `joined_at`

- `left_at` (nullable)




### CanvasDocument




- `id`

- `session_id`

- `schema_version`

- `latest_snapshot_id`

- `latest_operation_cursor`

- `updated_at`




### CanvasSnapshot




- `id`

- `canvas_document_id`

- `operation_cursor`

- `storage_key`

- `checksum`

- `created_at`




### CanvasOperation




- `id`

- `canvas_document_id`

- `actor_id`

- `client_operation_id`

- `payload`

- `server_received_at`




The exact operation schema depends on the selected CRDT. Canvas elements should still expose stable IDs, types, transforms, styles, text, connection endpoints, parent/group relationships, and creation/update metadata.




## 12. API surface




Illustrative HTTP endpoints:




| Method | Endpoint | Purpose |

| --- | --- | --- |

| `POST` | `/v1/sessions` | Create a session |

| `GET` | `/v1/sessions` | List owned or invited sessions |

| `GET` | `/v1/sessions/{id}` | Read session metadata |

| `PATCH` | `/v1/sessions/{id}` | Update prompt, title, or controls |

| `POST` | `/v1/sessions/{id}/start` | Start a session |

| `POST` | `/v1/sessions/{id}/end` | End a session |

| `POST` | `/v1/sessions/{id}/guest-links` | Create or rotate a guest link |

| `DELETE` | `/v1/sessions/{id}/guest-links/{linkId}` | Revoke a guest link |

| `POST` | `/v1/join/{token}` | Validate token and create guest participation |

| `GET` | `/v1/sessions/{id}/canvas` | Obtain snapshot and collaboration credentials |

| `POST` | `/v1/sessions/{id}/duplicate` | Duplicate as a new draft |




Illustrative WebSocket messages:




- Client to server: `join_room`, `document_update`, `presence_update`, `ping`

- Server to client: `room_joined`, `document_update`, `presence_snapshot`, `presence_update`, `permission_changed`, `session_ended`, `error`, `pong`




Every message includes a protocol version, session ID where relevant, and correlation or operation ID. The server validates membership and edit permission for every persistent update; joining a room once is not sufficient authorization.




## 13. Security and privacy requirements




- Guest tokens must contain at least 128 bits of cryptographic entropy.

- Tokens must be transmitted only over HTTPS, excluded from analytics payloads and application logs, and stored only as hashes.

- Session and canvas access must be authorized server-side for every API and socket action.

- Use short-lived collaboration credentials after the initial guest-link exchange so the bearer link is not repeatedly transmitted.

- Rate-limit join attempts, session creation, WebSocket connections, and document updates.

- Validate operation size, object count, text length, and supported element types.

- Sanitize all user-provided text before HTML rendering or export.

- Encrypt data in transit and at rest.

- Record audit events for session creation, link rotation/revocation, participant removal, permission changes, and session end.

- Define configurable retention and deletion rules before production launch.

- Avoid recording private interview content in product analytics.




## 14. Performance and reliability targets




| Metric | MVP target |

| --- | --- |

| Canvas usable after join | p95 under 3 seconds for a normal document |

| Remote operation propagation | p95 under 250 ms in-region, excluding user network |

| Reconnect after brief network loss | p95 under 5 seconds after connectivity returns |

| Concurrent participants per room | 10 |

| Typical supported canvas | 2,000 elements and 10,000 freehand points without material interaction lag |

| Monthly service availability | 99.9% after general availability |

| Confirmed-operation durability | No acknowledged persistent update lost after a single-instance failure |




Load limits must be tested using realistic freehand strokes and connector updates, not only simple rectangles.




## 15. Observability




Capture:




- Session creation, join success/failure, start, and end rates

- Time from page load to usable canvas

- Active WebSocket connections and rooms

- Operation ingress, fan-out latency, rejection rate, and payload size

- Reconnect count and duration

- Snapshot age, creation latency, and failure count

- Client render frame time and document size bands

- API and socket errors grouped by stable error code




Telemetry must use opaque identifiers and exclude prompts, labels, freehand content, guest tokens, and exported images.




## 16. MVP acceptance criteria




The MVP is accepted when all of the following are true:




1. An authenticated interviewer can create a session and copy a candidate link.

2. Two guest candidates and two authenticated interviewers can join the same session concurrently.

3. All four participants see component creation, movement, resizing, deletion, text edits, connections, and freehand strokes converge to the same state.

4. Simultaneous edits to different objects do not overwrite one another.

5. A participant who loses connectivity for 15 seconds reconnects and converges without manually reloading.

6. Refreshing the browser restores the latest confirmed canvas state.

7. The owner can lock candidate editing; candidate editing attempts are rejected by the server and reflected clearly in the UI.

8. Revoking a candidate link prevents new joins without disconnecting current participants unless the owner explicitly removes them.

9. Ending a session makes it read-only for candidates and creates a final saved snapshot.

10. A candidate cannot access another session by changing an identifier in an API request or WebSocket message.

11. The canvas remains interactive at the documented typical-canvas limit on the supported browser matrix.

12. Critical user flows meet keyboard and screen-reader requirements for the surrounding interface.




## 17. Delivery phases




### Phase 1 — Canvas foundation




- Single-user canvas

- Component palette

- Connectors, text, freehand, selection, pan, and zoom

- Local undo/redo

- Canvas serialization and schema versioning




### Phase 2 — Live collaboration




- Collaboration document and WebSocket gateway

- Multi-user synchronization

- Presence, cursors, selections, reconnect, and autosave

- Snapshot and operation compaction




### Phase 3 — Interview workflow




- Interviewer authentication and dashboard

- Session creation and candidate links

- Lobby, roles, permissions, editing lock, and end flow

- Security, audit events, and retention controls




### Phase 4 — Production readiness




- Browser and accessibility verification

- Load, reconnect, and failure testing

- Monitoring, alerts, abuse limits, support tooling, and incident runbooks

- Optional initial export functionality




## 18. Product decisions still required




Before implementation, stakeholders should decide:




1. Whether candidate links reveal the prompt immediately or only after the interviewer starts the session.

2. Whether candidates may re-enter an ended session in read-only mode.

3. Default data-retention period and who may permanently delete a session.

4. Whether additional interviewers can lock editing or end a session.

5. Whether interviewers require organization accounts in the first release.

6. Whether PNG/PDF export is required for launch or can follow the MVP.

7. Expected largest customer, concurrent session count, and geographic regions; these affect collaboration architecture and capacity planning.

8. Whether a timer is merely visible or automatically changes session state.




## 19. Recommended next artifact




The next design step should be a clickable UX prototype covering five screens: interviewer dashboard, create-session form, candidate lobby, live interview canvas, and ended-session review. In parallel, engineering should run a short technical spike comparing suitable canvas renderers and CRDT approaches against the acceptance criteria, especially connectors, text editing, freehand performance, scoped undo, and reconnect behavior.

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/d8f85319-bdc7-450a-8f38-5499e78f10e7).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
