# Wallet + Transaction DB Table Design

This design uses a **hybrid ledger model**:

- `wallets.current_balance` is stored for fast display.
- `wallet_transactions` is the source of truth for all balance changes.
- Balance must never be overwritten directly from UI/business code.
- Every balance change must create a transaction record inside one atomic database transaction.

Recommended database: PostgreSQL.

---

## 1. Core Rule

Wallet balance is visible to users, agents, and admin, but it is updated only through ledger transactions.

Wrong:

```sql
UPDATE wallets SET current_balance = 5000 WHERE wallet_id = '...';
```

Correct:

```text
1. Lock parent wallet row.
2. Lock child wallet row.
3. Validate hierarchy and available balance.
4. Insert transaction ledger row.
5. Update wallet balances based on that transaction.
6. Commit.
```

---

## 2. Money Precision

Use `NUMERIC(18, 3)` for all wallet and transaction amounts.

Why:

- Supports 3 digits after decimal.
- Avoids floating-point errors.
- Suitable for wallet/betting calculations.

Examples:

```text
10.000
99.125
1500.750
```

---

## 3. Table: wallets

Stores the latest wallet snapshot for fast balance lookup.

```sql
CREATE TABLE wallets (
    wallet_id UUID PRIMARY KEY,

    owner_id UUID NOT NULL,
    owner_type VARCHAR(20) NOT NULL CHECK (owner_type IN ('ADMIN', 'AGENT', 'USER')),

    current_balance NUMERIC(18, 3) NOT NULL DEFAULT 0.000 CHECK (current_balance >= 0),

    currency VARCHAR(10) NOT NULL DEFAULT 'UNIT',

    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
        CHECK (status IN ('ACTIVE', 'LOCKED', 'FROZEN', 'CLOSED')),

    version BIGINT NOT NULL DEFAULT 0,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (owner_id, owner_type)
);
```

### Column Meaning

| Column | Meaning |
|---|---|
| `wallet_id` | Unique wallet id |
| `owner_id` | Admin/Agent/User id |
| `owner_type` | Type of wallet owner |
| `current_balance` | Fast balance display value |
| `currency` | Game unit/currency identifier |
| `status` | Wallet operational status |
| `version` | Used for optimistic locking |
| `created_at` | Wallet creation time |
| `updated_at` | Last wallet update time |

---

## 4. Table: wallet_transactions

This is the ledger table. Every money movement must be recorded here.

```sql
CREATE TABLE wallet_transactions (
    transaction_id UUID PRIMARY KEY,

    idempotency_key VARCHAR(120) NOT NULL UNIQUE,

    transaction_type VARCHAR(30) NOT NULL CHECK (
        transaction_type IN (
            'PARENT_TO_CHILD_CREDIT',
            'PARENT_FROM_CHILD_DEBIT',
            'BET_DEBIT',
            'BET_WIN_CREDIT',
            'BET_REFUND',
            'ADMIN_ADJUSTMENT'
        )
    ),

    direction VARCHAR(20) NOT NULL CHECK (
        direction IN ('CREDIT', 'DEBIT', 'TRANSFER')
    ),

    from_wallet_id UUID NULL REFERENCES wallets(wallet_id),
    to_wallet_id UUID NULL REFERENCES wallets(wallet_id),

    initiated_by_user_id UUID NOT NULL,
    initiated_by_user_type VARCHAR(20) NOT NULL CHECK (initiated_by_user_type IN ('ADMIN', 'AGENT', 'SYSTEM')),

    amount NUMERIC(18, 3) NOT NULL CHECK (amount > 0),

    fee_amount NUMERIC(18, 3) NOT NULL DEFAULT 0.000 CHECK (fee_amount >= 0),
    net_amount NUMERIC(18, 3) NOT NULL CHECK (net_amount >= 0),

    balance_before_from NUMERIC(18, 3) NULL,
    balance_after_from NUMERIC(18, 3) NULL,

    balance_before_to NUMERIC(18, 3) NULL,
    balance_after_to NUMERIC(18, 3) NULL,

    reference_type VARCHAR(40) NULL,
    reference_id UUID NULL,

    status VARCHAR(20) NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'SUCCESS', 'FAILED', 'REVERSED')),

    failure_reason TEXT NULL,
    remarks TEXT NULL,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL
);
```

### Column Meaning

| Column | Meaning |
|---|---|
| `transaction_id` | Unique ledger transaction id |
| `idempotency_key` | Prevents duplicate transaction on retry |
| `transaction_type` | Business reason for transaction |
| `direction` | Credit, debit, or transfer |
| `from_wallet_id` | Wallet money is deducted from |
| `to_wallet_id` | Wallet money is credited to |
| `initiated_by_user_id` | Who initiated the transaction |
| `amount` | Original amount |
| `fee_amount` | Fee, for example 5% betting commission |
| `net_amount` | Final credited amount after fee |
| `balance_before_from` | Sender balance before transaction |
| `balance_after_from` | Sender balance after transaction |
| `balance_before_to` | Receiver balance before transaction |
| `balance_after_to` | Receiver balance after transaction |
| `reference_type` | Related object type, for example `BET` or `GAME_SESSION` |
| `reference_id` | Related object id |
| `status` | Transaction lifecycle state |
| `failure_reason` | Failure details if transaction failed |
| `remarks` | Admin/Agent note |
| `created_at` | Transaction creation time |
| `completed_at` | Successful completion time |

---

## 5. Transaction Types Explained

### 5.1 Add Money: Parent → Immediate Child

Example: Admin adds 100.000 to immediate Agent.

```text
transaction_type = PARENT_TO_CHILD_CREDIT
from_wallet_id   = admin_wallet_id
to_wallet_id     = agent_wallet_id
amount           = 100.000
net_amount       = 100.000
```

Effect:

```text
Admin wallet  -100.000
Agent wallet  +100.000
```

---

### 5.2 Deduct Money: Immediate Child → Parent

Example: Agent deducts 50.000 from immediate User.

This is not direct balance editing. It is a reverse ledger transfer.

```text
transaction_type = PARENT_FROM_CHILD_DEBIT
from_wallet_id   = user_wallet_id
to_wallet_id     = agent_wallet_id
amount           = 50.000
net_amount       = 50.000
initiated_by     = parent agent
```

Effect:

```text
User wallet   -50.000
Agent wallet  +50.000
```

Important:

- The parent initiates the deduction.
- The child wallet is debited only through a transaction record.
- The ledger history permanently shows why the money moved.

---

### 5.3 Bet Deduction

Before game starts, bet amount is deducted.

```text
transaction_type = BET_DEBIT
from_wallet_id   = player_wallet_id
to_wallet_id     = system/game_pool_wallet_id
amount           = bet_amount
reference_type   = BET
reference_id     = bet_id
```

Effect:

```text
Player wallet    -bet_amount
Game pool wallet +bet_amount
```

---

### 5.4 Winning Payout

For winning side:

```text
payout = bet_amount + (bet_amount - 5% of bet_amount)
       = bet_amount + 95% of bet_amount
       = 1.95 * bet_amount
```

Example bet = 100.000:

```text
payout = 100.000 + 95.000 = 195.000
```

Transaction:

```text
transaction_type = BET_WIN_CREDIT
from_wallet_id   = system/game_pool_wallet_id
to_wallet_id     = winner_wallet_id
amount           = 195.000
fee_amount       = 5.000
net_amount       = 195.000
reference_type   = GAME_SESSION
reference_id     = game_session_id
```

---

## 6. Required Indexes

```sql
CREATE INDEX idx_wallet_owner
ON wallets(owner_id, owner_type);

CREATE INDEX idx_wallet_tx_from_wallet
ON wallet_transactions(from_wallet_id, created_at DESC);

CREATE INDEX idx_wallet_tx_to_wallet
ON wallet_transactions(to_wallet_id, created_at DESC);

CREATE INDEX idx_wallet_tx_reference
ON wallet_transactions(reference_type, reference_id);

CREATE INDEX idx_wallet_tx_created_at
ON wallet_transactions(created_at DESC);

CREATE INDEX idx_wallet_tx_status
ON wallet_transactions(status);
```

---

## 7. Atomic Transfer Flow

All wallet updates must happen inside a single database transaction.

Pseudo-flow:

```text
BEGIN TRANSACTION

1. Check idempotency_key.
   - If already SUCCESS, return existing transaction.
   - If already PENDING, reject or wait.

2. Validate initiator permission.
   - Admin can transact only with immediate child agents.
   - Agent can transact only with immediate child agents/users.
   - User cannot transfer money.

3. Lock wallets in deterministic order.
   - SELECT ... FOR UPDATE
   - Always lock smaller wallet_id first to avoid deadlocks.

4. Validate wallet statuses.
   - Both wallets must be ACTIVE.

5. Validate sufficient balance in debit wallet.
   - Prevent negative balance.
   - Prevent double spending.

6. Insert wallet_transactions row as PENDING.

7. Update wallet balances.
   - Debit from_wallet.
   - Credit to_wallet.
   - Increment version.

8. Update wallet_transactions row as SUCCESS.
   - Store before/after balances.
   - Store completed_at.

COMMIT
```

On any failure:

```text
ROLLBACK
```

---

## 8. Row-Level Locking Example

```sql
BEGIN;

SELECT wallet_id, current_balance, status
FROM wallets
WHERE wallet_id IN (:from_wallet_id, :to_wallet_id)
ORDER BY wallet_id
FOR UPDATE;

-- validate balance and status
-- insert transaction
-- update balances

COMMIT;
```

---

## 9. Balance Validation Query

This query checks whether stored wallet balance matches ledger history.

```sql
SELECT
    w.wallet_id,
    w.current_balance AS stored_balance,
    COALESCE(SUM(
        CASE
            WHEN wt.to_wallet_id = w.wallet_id AND wt.status = 'SUCCESS' THEN wt.net_amount
            WHEN wt.from_wallet_id = w.wallet_id AND wt.status = 'SUCCESS' THEN -wt.amount
            ELSE 0
        END
    ), 0.000) AS ledger_balance
FROM wallets w
LEFT JOIN wallet_transactions wt
    ON wt.to_wallet_id = w.wallet_id
    OR wt.from_wallet_id = w.wallet_id
GROUP BY w.wallet_id, w.current_balance
HAVING w.current_balance <> COALESCE(SUM(
    CASE
        WHEN wt.to_wallet_id = w.wallet_id AND wt.status = 'SUCCESS' THEN wt.net_amount
        WHEN wt.from_wallet_id = w.wallet_id AND wt.status = 'SUCCESS' THEN -wt.amount
        ELSE 0
    END
), 0.000);
```

If this query returns rows, wallet balance and ledger are inconsistent and must be investigated.

---

## 10. Recommended Additional Tables Later

For full production design, these tables should also exist:

```text
users
hierarchy_edges or user_parent_relation
bets
game_sessions
game_results
wallet_audit_logs
admin_action_logs
```

But for wallet correctness, the two most important tables are:

```text
wallets
wallet_transactions
```

---

## 11. Final Design Decision

Use this approach:

```text
Stored wallet balance = fast display value
Transaction ledger    = source of truth
All changes           = atomic ledger transaction only
Direct overwrite      = forbidden
```
