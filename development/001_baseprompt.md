# The Base Prompt

Codex will start reading from this prompt

- Codex will ignore the prompt where `status` is **Done**
- Codex will focus on the prompts where `status` is **Ongoing**


---
## prompt - 001 
`status` : **Done**
```
1. check all prompt files in ./prompts
2. check all dragram fils in ./diagrams
3. check tin patti game template in ./template
4. check test_server_sunced.py
5. check tin_patti_modified.py

```
```
now build an initial web application 

the target folder of the webapplication ./using_chatgpt
```
---
---

## prompt - 002 
`status` : **Done**
```
1. check all prompt files in ./prompts
2. check all dragram fils in ./diagrams
3. check the existing webapplication in ./using_chatgpt
4. check generate_id() method in Person class inside of ./dev_time_utlils/classes.py
```
```
modify the webapplication based on the following points
1. read ADMIN_EMAIL_ID from .env file

2. Admin should have proper login with captcha validation, email otp validation (Use smtp in celery task with proper error handling)

3. Agent should also have proper login with captcha validation, email otp validation (Use smtp in celery task with proper error handling)

4. User should also have proper login with captcha validation

5. There will be a button at the time of agent or user ceration named "generate id and password" which will generate id based on generate_id() method {inside Person class inside of ./dev_time_utlils/classes.py}. there will be a random 8 to 10 character password generator logic, which will take current date time as input, and other complex stuff to generate a strong passwrd

6. when the user is created (after clicking create button) its parent agent will get an confirmation mail with use id and password details , that the usr with this id and this password is created at ___ time.

7. when the agent is created (after clicking create button) its parent agent/Admin will get an confirmation mail with agent id and password details , that the agent with this id and this password is created at ___ time. the created agent will also get the email of its id and password and creation and creator agent / admin id

8. Admin can itself update its money (add or substract), initially when the server will be started, then the admin amount will be 0 (if in db there is no previous record, otherwise admin amount will be previously stored amount value)

9. initial amount of created agent or user will be 0 (there immidiate parent can only update the immidiate childrens amount, i think it is already implemented, please check)



now update the existing web application 

the target folder of the webapplication ./using_chatgpt itself
```
---
---
## prompt - 003 
`status` : **Done**
```
1. check all prompt file ./prompts
2. check all dragram fils in ./diagrams
3. check the existing webapplication in ./using_chatgpt
3. check andar bahar game template ./template/andar_bahar_synced.html
4. check andar_bahar_server_synced.py
5. check andar_bahar_modified.py

```
```
now well maintainable modular way add this andar bahar game into the game list of existing web application, like tin patti game.

who ever wants to play can see both game in a webpage as a list, after clicking they can enter the particular game console to play the game

one player can play a game at a time (which will make some transaction safty) (if one player enters into a game, and bids and game starts, he can go back to game list page but he have to wait until, his existing game finishes, then he can enter into another game)

check in tinpatti, last 10 winner records are kept or not, as it will be required in the front end , must come from backend. do the same thing for the andar bahar game

make the andar bahar core logic efficient like, the tinpatti core logic, proper exception handling without crashing

in the web page where all games are listed, player can see his id and existing amount, and a refresh amount button so that if its immidiate parent updates the playes amount then that can be shown.

in any particular game webpage player can see his id and existing amount, and a refresh amount button so that if its immidiate parent updates the playes amount then that can be shown. make a bidding system , so that during biding time , player can bid for a hand A or B with its amount in hand.

make sure each games have their own static files (also make static files efficient, you can keep common stuffs in common place, that is up to you)

the target folder of the webapplication ./using_chatgpt

if you have any question please ask me.

do the smtp setup with app password

make sure previous working logics (which are not going to be changed) are not broken

```
---
---
