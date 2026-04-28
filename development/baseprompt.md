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
`status` : **Ongoing**
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