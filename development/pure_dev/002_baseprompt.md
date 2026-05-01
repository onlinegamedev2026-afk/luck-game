# The Base Prompt

Codex will start reading from this prompt

- Codex will ignore the prompt where `status` is **Done**
- Codex will focus on the prompts where `status` is **Ongoing**


---
## prompt - 004 
`status` : **Done**
```
1. check the existing webapplication in ./using_chatgpt
```
```
now do an update, I want no emails should store in the sent items of the sender email id

the target folder of the webapplication ./using_chatgpt
```
---
---
## prompt - 005 
`status` : **Done**
```
1. check the existing webapplication in ./using_chatgpt
```
```

now do the following updates :-

1. If any agent is inactive, all children under that agent will also become inactive. Inactive accounts cannot log in.
   If the inactive agent or any inactive child is currently inside a game, then after the game is over and after all associated transactions are completed, make them logged out and redirect them to the home page.

2. If an Agent or User is inactive, then during login attempt failure, instead of showing "invalid login credentials", show this message:
   "Currently you are inactive please contact your agent"

3. If any agent is removed, then all of its children will be removed as well. If the removed agent or any removed child is currently inside a game, then after the game is over and after all associated transactions are completed, make them logged out and redirect them to the home page. After removal, they obviously cannot log in because their accounts are removed.

4. The ID of Admin will be "admin", and the wallet ID of Admin will be "admin_wallet".

5. Admin, Agent, and User home pages will have an "Update Password" button. On clicking it, a form will appear, preferably in a card or any better format, where the user provides:

   * old password
   * new password
   * update button

6. In Admin and Agent home pages, in each row of their immediate children list, there will be one button called "Regenerate Password". There will be a newly generated read-only output field, where the new password will be shown.
   On clicking it, one new password will be generated for that immediate child.
   This means any Admin or Agent can regenerate only their immediate child’s password.

After clicking the button:

* If the child is an Agent, then the child Agent and its parent will both get an email regarding password update.
* If the child is a User, then only its parent will get an email regarding password update.

7. In Agent home page, there will be a button whose name will toggle between:

   * "All"
   * "Only Users"
   * "Only Agents"

On clicking the button, toggling will happen.
When the name is "All", the immediate children list will contain both Users and Agents.
When the name is "Only Users", the immediate children list will contain only Users.
When the name is "Only Agents", the immediate children list will contain only Agents.

8. In Admin and Agent home pages, every time only 20 immediate children will be shown in the list.
   There will be "Next" and "Previous" buttons, which will show the next 20 or previous 20 children.

9. There is already a search option like search by name and ID.
   After search, the matched immediate children will be shown in the list.
   This search result list will also show at most 20 rows at a time, with pagination if needed.

10. The wallet amount shown for User, Admin, or Agent should be brighter and easier to recognize visually.

11. The OTP validation time will be 30 minutes. If there is a "Send OTP" button, then proper rate limiting must be applied behind it using the best possible logic (e.g., request throttling, cooldown timers, and abuse prevention).

Do not break any existing logic that is not being changed.

The target folder of the web application is:
./using_chatgpt

```
---
---
## prompt - 006 
`status` : **Done**
```
1. check the existing webapplication in ./using_chatgpt
```
```
now do the following updates :- 
1. The email ID must be globally unique across the system. 
   This means no two Admins, Agents, or Users can share the same email ID. 
   An email ID used by an Admin cannot be used by an Agent or User, and vice versa.
   if required clean the entire database first then implement that

Do not break any existing logic that is not being changed.

the target folder of the webapplication ./using_chatgpt
```
---
---
## prompt - 007 
`status` : **Done**
```
1. check the existing webapplication in ./using_chatgpt
```
```
Now apply the following updates to the web application in the target folder:

Target folder:
./using_chatgpt

Important:
Do not break or modify any existing logic unless it is directly required for the updates below.

Updates:

1. Agent reactivation logic
   - If any inactive Agent is reactivated, then all of its children at every level must also be reactivated.
   - This includes child Agents, sub-child Agents, and Users under that Agent.

2. Dashboard wallet action label update
   - In the Admin dashboard and Agent dashboard, inside the immediate child list section:
     - Replace the “+Money” button with “+Units”.
     - Replace the “-Money” button with “-Units”.
   - Only the button labels/text should change unless backend naming changes are absolutely required.

3. Common game flow logic for all games

   3.1 Transaction handling
   - Ensure all game-related transactions work correctly before, during, and after the game.
   - Betting must be tracked team-wise/hand-wise, for example:
     - Team/Hand A total betting amount
     - Team/Hand B total betting amount
   - After the winner is declared:
     - Winning team users must receive the correct credited amount.
     - Losing team users must have the correct deducted amount as per the existing/prior transaction rules.
   - Ensure wallet/unit balances, transaction records, and game result records remain consistent.

   3.2 Betting session before game
   - Before every game starts, there must be a 30-second betting session.
   - During this time, users can place bets [give some way so that player can bet, check this area].
   - Show a countdown message:
     “Betting time pending: X seconds”

   - After the 30-second betting session ends, start a 10-second cooldown/initiation session.
   - During this cooldown:
     - No more bets should be accepted.
     - Show a countdown message:
       “Game is being initiated in X seconds”
     - Backend should calculate total betting amount per team/hand and any other required game data.
     - These calculated values must remain hidden from normal Users.
     - Only Admins and Agents can see total betting amount per team/hand.

   3.3 After-game cooldown
   - After the game ends and the winning team/hand is declared, start a 5-second cooldown.
   - During this cooldown:
     - All pending transactions and wallet/unit updates must be completed.
     - Show a countdown message:
       “Next betting will start within X seconds”

   3.4 Player permissions
   - Players/Users can only place bets.
   - All other game actions must be automated and time-dependent.
   - Game lifecycle:
     - Betting time: 30 seconds
     - Pre-game cooldown/initiation time: 10 seconds
     - Gameplay time: based on the game’s existing logic
     - After-game cooldown: 5 seconds

   3.5 Game must always run
   - The game must run every cycle, even if no users place bets.
   - Cases:
     - If there is no betting on either side:
       - Game should still be played.
       - No user transactions are required after the game.
     - If betting happens on only one side:
       - Game should still be played.
       - Transactions must happen based on the declared winner and existing/prior payout rules.
     - If betting happens on both sides:
       - Game should run normally.
       - Transactions must happen correctly after winner declaration.

   3.6 Minimum bet
   - Minimum bet amount per player is 10 units.
   - Reject any bet below 10 units with a proper validation message.

Final requirement:
After implementing the updates, review the affected files and ensure:
- Existing login, wallet, dashboard, agent hierarchy, and game logic are not broken.
- Transaction handling is concurrency-safe.
- No user can place bets outside the active betting session.
- Admin and Agents can view total betting amounts per team/hand only after the betting phase ends and until the current game cycle completes; this information must remain hidden from Users at all times.
```
---
---
