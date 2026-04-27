You are a senior backend architect specializing in scalable real-time game platforms.

I am building a web application that hosts multiple simple online games (e.g., Teen Patti). I need a **production-grade Low-Level Design (LLD)** in Python.

IMPORTANT: Do NOT jump directly into code. First think structurally and ensure correctness of hierarchy, transactions, concurrency, and extensibility.

---

## 🧠 SYSTEM CONTEXT

There are 3 types of users:

1. **Admin**

   * Only ONE exists
   * Created before system start
   * Cannot be deleted

2. **Agent**

   * Created by Admin or another Agent
   * Can create:

     * Agents
     * Users

3. **User**

   * Created by Agents

✅ IMPORTANT:

* Admin, Agents, and Users — ALL can play games
* ALL entities (Admin, Agent, User) have **wallets**

---

## ⚠️ HIERARCHY RULES (STRICT)

1. Admin can create Agents only

2. Agents can create Agents and Users

3. Hierarchical ownership (tree structure)

4. If an Agent is deleted:

   * All child Agents and Users must be reassigned to its parent Agent

5. Top-level Agents (under Admin):

   * Cannot be deleted directly
   * Their children must first be reassigned to another top-level Agent

6. Admin can NEVER be deleted

---

## 💰 WALLET & TRANSACTION RULES (CRITICAL)

### 💳 Wallet

* Every entity has a wallet
* All monetary values must support **3 decimal precision (.3f)**
* DO NOT use float — use Decimal-like abstraction

---

### 🔁 Transaction Flow (STRICT)

Transactions are ONLY allowed as:

* Admin → its child Agents
* Agent → its child Agents
* Agent → its child Users

❌ NOT ALLOWED:

* Direct balance overwrite
* Arbitrary transfers outside hierarchy

---

### 🚫 NO DIRECT BALANCE UPDATE

* All balance updates MUST happen via **transactions**
* Use **ledger-based accounting**
* Balance should be **derived**, not directly stored (or if stored, must be consistent with ledger)

---

### 🔐 TRANSACTION SAFETY (MANDATORY DESIGN COMMENTS)

For every money-related method, include:

* Atomic DB transactions
* Row-level locking OR optimistic locking
* Idempotency (retry-safe operations)
* Race condition prevention
* Rollback mechanism
* Double-spending prevention
* Ledger consistency validation

---

## 🎮 GAME SYSTEM CONSTRAINTS

### Game Execution Model

* Only **ONE instance of a specific game** runs at a time
* BUT multiple different games can run in parallel

Example:

* Teen Patti → 1 instance
* Another game → 1 instance

---

### ⚡ REAL-TIME ARCHITECTURE

System uses:

* WebSockets (Socket.IO style)
* Event-driven updates

Events include:

* game_started
* card_dealt
* game_result
* server_state (for reconnect sync)

Design must include:

* Separation of:

  * Game Engine
  * Game Orchestrator
  * Realtime Gateway

---

## 🎯 BETTING & GAME FLOW (IMPORTANT DOMAIN LOGIC)

This is generic logic that will apply to games:

1. Betting window: **30 seconds**
2. Players bet on one of two options (A or B)
3. Minimum bet: 10 units

---

### 💸 Betting Rules

Case 1:

* Both A and B have 0 bets → game still runs
* No deduction, no reward

Case 2:

* One side has 0, other non-zero → game runs

Case 3:

* Both have bets:

  * Losing side → all bets lost (0)
  * Winning side payout:

```
final_amount =
    (current_balance after deduction)
    + bet_amount
    + (bet_amount - 0.5% of bet_amount)
```

---

### ⚠️ IMPORTANT

* Bet amount must be **deducted BEFORE game starts**
* Settlement happens AFTER result

---

## 🧱 OUTPUT REQUIREMENTS

### 1. Clarifying Questions / Assumptions

* Some additional clarity may come later from draw.io diagram
* Clearly state assumptions if made

---

### 2. Folder Structure

Must include clear modular design:

```
project_root/
│
├── models/
├── services/
├── core/
├── transactions/
├── games/
│   ├── base_game.py
│   ├── teen_patti/
│   └── ...
├── realtime/
├── utils/
└── main.py
```

---

### 3. High-Level Design Summary

Explain:

* Architecture
* Concurrency safety
* Transaction safety
* Game extensibility
* WebSocket integration

---

## 🧱 PART 1: MODEL CLASSES (SINGLE SCRIPT)

These simulate DB tables (framework-independent).

### Must include:

* BaseUser (common parent)
* Admin
* Agent
* User
* Wallet
* Transaction (ledger)
* Bet
* GameSession
* GameResult

---

### For EACH class:

* Add file location comment
* Attributes with types
* Relationships (parent_id, etc.)
* Methods:

  * Only signatures
  * Detailed comments explaining logic
  * NO implementation

---

## ⚙️ PART 2: SERVICE / LLD CLASSES (SINGLE SCRIPT)

### Must include:

* AdminService
* AgentService
* UserService
* WalletService
* TransactionService
* BettingService
* GameService
* GameOrchestrator
* HierarchyService
* RealtimeService (Socket handling abstraction)

---

### Each method must include:

* Type hints
* Step-by-step logic in comments
* Edge cases
* Failure scenarios

---

## 🎮 GAME EXTENSIBILITY

Design a BaseGame class:

Methods:

* create_session()
* start_betting()
* stop_betting()
* start_game()
* calculate_result()
* settle_bets()

Explain:

* How new games plug in
* How GameOrchestrator uses them
* How minimal changes are required

---

## 🧩 DESIGN CONSTRAINTS

* Follow SOLID principles
* Prefer composition over inheritance
* Keep services loosely coupled
* Design for future microservices split
* Keep services mostly stateless (except orchestrator where needed)

---

## 🚫 WHAT NOT TO DO

* Do NOT write actual business logic
* Do NOT use frameworks (no Django/FastAPI ORM)
* Do NOT skip transaction safety comments
* Do NOT simplify hierarchy rules

---

## 📌 FUTURE INPUT

* System will be refined using draw.io diagrams and existing Python files
* Design must be adaptable

---

## ✅ FINAL OUTPUT

1. Clarifications / Assumptions
2. Folder Structure
3. High-Level Design
4. Model Classes (single script)
5. Service / LLD Classes (single script)

Make the design detailed enough so that another AI can directly convert it into production-ready backend code.
