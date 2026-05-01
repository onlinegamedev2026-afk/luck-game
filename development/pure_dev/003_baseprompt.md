# The Base Prompt

Codex will start reading from this prompt

- Codex will ignore the prompt where `status` is **Done**
- Codex will focus on the prompts where `status` is **Ongoing**

---
## prompt - 008
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

All the games (tin patti and andar bahar) should follow the following game cycle rules.
strictly in ui and backend

1st: betting cycle (40s)
    message: "Betting will be over within X seconds"
        X from 40s to 0s countdown
    this time player can bet. a player can see all of its bets placed for that game cycle
    previous total bets per team will set to 0 (which Agent and Admin can only see)

2nd: cooling cycle (20s)
    message: "Game will be initiated within X seconds"
        X from 20s to 0s countdown
    do all necessery transaction (like total bet amount per team calculation done for this game cycle) (which Agent and Admin can only see)

3rd: the game itself started and being played and winner decided

4th: cooling cycle (20s)
    message: "Betting for next game will start within X seconds"
        X from 20s to 0s countdown
    complete pending transactions
```
---
---
