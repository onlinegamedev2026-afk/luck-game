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

## ⚠️ HIERARCHY RULES (UPDATED — VERY IMPORTANT)

1. Admin can create Agents only
2. Agents can create Agents and Users
3. Hierarchical ownership (tree structure)

---

### 🗑️ DELETION RULES (STRICT — UPDATED)

1. **Admin can delete ONLY its immediate Agents**

   * When Admin deletes an Agent:

     * That Agent AND **ALL its descendants (Agents + Users)** are permanently deleted

2. **Agents can delete ONLY their immediate children**

   * If deleting a **User** → delete that user
   * If deleting an **Agent** → delete that agent AND **ALL its descendants**

3. **No reassignment of children**

   * Deletion always results in full subtree removal

4. **Admin can NEVER be deleted**


---

## UI / FLOW ALIGNMENT FROM DRAW.IO

The LLD must also reflect the uploaded draw.io flow:

1. Login screens:

   * Admin Login
   * Agent Login
   * User Login
   * Captcha / OTP where applicable

2. Admin Home:

   * Shows wallet amount in hand
   * Lists immediate child agents only
   * Search agents by name or id
   * Add Agent
   * Remove Agent
   * Activate / Deactivate Agent
   * Add money / deduct money for immediate child agents
   * Download last 30 days transaction details
   * Download all agent details
   * Change password
   * Play game

3. Agent Home:

   * Shows wallet amount in hand
   * Lists immediate child agents and users
   * Search child agent/user by name or id
   * Add Agent
   * Add User
   * Remove immediate child agent/user
   * Activate / Deactivate child agent/user
   * Add money / deduct money for immediate children
   * Download last 30 days transaction details
   * Download all child agent/user details
   * Change password
   * Play game

4. User Home:

   * Shows client id
   * Shows wallet amount
   * Can play available games
   * Cannot create users or agents
   * Cannot transfer money

5. Deletion rule must strictly match:

   * Admin can delete only immediate child agents.
   * Agent can delete only immediate child agents/users.
   * If deleted child is an agent, delete the entire subtree below that agent.
   * No reassignment of descendants.

6. Wallet buttons `+ money` and `- money` must be modeled as ledger transactions only.

   * No direct balance overwrite.
   * Only parent → immediate child transaction direction is valid.
   * Deduct money should be represented as a reverse/negative ledger entry initiated by the authorized parent, not a direct mutation.

7. Activate / Deactivate:

   * Soft status change only.
   * Deactivated accounts cannot login, play games, place bets, or receive/send wallet transactions.
   * Deactivation does NOT delete wallet ledger history.

---

## 💰 WALLET & TRANSACTION RULES (CRITICAL)

### 💳 Wallet

* Every entity has a wallet
* All monetary values must support **3 decimal precision (.3f)**
* DO NOT use float — use Decimal-like abstraction

---

### 🔁 Transaction Flow (STRICT)

Transactions are ONLY allowed as:

* Admin → its immediate child Agents
* Agent → its immediate child Agents
* Agent → its immediate child Users

❌ NOT ALLOWED:

* Direct balance overwrite
* Transfers outside hierarchy

---

### 🚫 NO DIRECT BALANCE UPDATE

* All balance updates MUST happen via **transactions**
* Use **ledger-based accounting**
* Balance should be **derived** (or strictly validated if stored)

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
* Multiple different games can run in parallel

---

### ⚡ REAL-TIME ARCHITECTURE

System uses:

* WebSockets (Socket.IO style)
* Event-driven updates

Events include:

* game_started
* card_dealt
* game_result
* server_state

Design must include:

* Game Engine
* Game Orchestrator
* Realtime Gateway

---

## 🎯 BETTING & GAME FLOW

1. Betting window: **30 seconds**
2. Players bet on one of two options (A or B)
3. Minimum bet: 10 units

---

### 💸 Betting Rules

Case 1:

* Both A and B have 0 bets → game runs, no effect

Case 2:

* One side 0 → game runs normally

Case 3:

* Both have bets:

  * Losing side → all bets lost
  * Winning side payout:

```
final_amount =
    (balance after deduction)
    + bet_amount
    + (bet_amount - 5% of bet_amount)
```

---

### ⚠️ IMPORTANT

* Bet amount deducted BEFORE game starts
* Settlement AFTER result

---

## 🧱 OUTPUT REQUIREMENTS

### 1. Clarifications / Assumptions

---

### 2. Folder Structure

```
project_root/
├── models/
├── services/
├── core/
├── transactions/
├── games/
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
* Realtime flow

---

## 🧱 PART 1: MODEL CLASSES (SINGLE SCRIPT)

Must include:

* BaseUser
* Admin
* Agent
* User
* Wallet
* Transaction
* Bet
* GameSession
* GameResult

Each class:

* File location comment
* Attributes with types
* Relationships
* Method signatures ONLY
* Detailed comments (NO implementation)

---

## ⚙️ PART 2: SERVICE / LLD CLASSES

Must include:

* AdminService
* AgentService
* UserService
* WalletService
* TransactionService
* BettingService
* GameService
* GameOrchestrator
* HierarchyService
* RealtimeService

Each method:

* Type hints
* Step-by-step comments
* Edge cases
* Failure scenarios

---

## 🎮 GAME EXTENSIBILITY

BaseGame must include:

* create_session()
* start_betting()
* stop_betting()
* start_game()
* calculate_result()
* settle_bets()

Explain plug-in architecture clearly.

---

## 🧩 DESIGN CONSTRAINTS

* SOLID principles
* Loose coupling
* Composition preferred
* Future microservice-ready
* Mostly stateless services

---

## 🚫 WHAT NOT TO DO

* No framework usage
* No business logic implementation
* No skipping transaction safety
* No simplification of hierarchy

---

## 📌 FUTURE INPUT

* Will be refined via draw.io and existing code

---

## ✅ FINAL OUTPUT

1. Clarifications / Assumptions
2. Folder Structure
3. High-Level Design
4. Model Classes
5. Service Classes

Design must be detailed enough for direct production conversion.
