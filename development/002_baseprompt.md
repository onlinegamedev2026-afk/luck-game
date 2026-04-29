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