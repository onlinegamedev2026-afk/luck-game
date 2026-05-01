import datetime as dt
from uuid import uuid4
from typing import Literal
from random import randint

#TODO email id is not mandatory for normal user

class Person:
    def __init__(
        self,
        full_name: str,
        _id: str,
        super_id: str,
        is_active: bool,
        rank: Literal["admin", "agent", "user"],
        password: str,
        email: str,
        creation_time: dt.datetime,
        last_edit_time: dt.datetime,
        last_login_time: dt.datetime,
        amount: float,
    ) -> None:
        self.full_name: str = full_name
        self._id: str = _id
        self.super_id: str = super_id
        self.is_active: bool = is_active
        self.rank: Literal["admin", "agent", "user"] = rank
        self.password: str = password
        self.email: str = email
        self.creation_time: dt.datetime = creation_time
        self.last_edit_time: dt.datetime = last_edit_time
        self.last_login_time: dt.datetime = last_login_time
        self.amount: float = amount
    
    def update_password(self, new_password: str,confirm_password: str, old_password: str) -> bool:
        if old_password != self.password:
            return False
        if new_password == confirm_password and new_password != self.password:
            self.password = new_password
            return True
        return False
    
    def verify_email(self) -> bool:
        # Implement email verification logic here
        return True
    
    @staticmethod
    def generate_id(full_name: str) -> str:
        creation_time: dt.datetime = dt.datetime.now()
        sanitized_name: str = full_name.strip().replace(" ", "").lower()
        return f"{sanitized_name}@{creation_time.strftime('%S%f')[:5]}#{randint(1000, 9999)}"


class Admin(Person):
    def __init__(
        self,
        full_name: str,
        _id: str,
        is_active: bool,
        password: str,
        email: str,
        creation_time: dt.datetime,
        last_edit_time: dt.datetime,
        last_login_time: dt.datetime,
        amount: float,
    ) -> None:
        super().__init__(full_name, _id, "ROOT", is_active, "admin", password, email, creation_time, last_edit_time, last_login_time, amount)

    def __repr__(self) -> str:
        return f"Admin({self._id}, {self.full_name}, {self.super_id}, {self.is_active}, {self.rank}, {'********'}, {self.email}, {self.creation_time}, {self.last_edit_time}, {self.last_login_time}, {self.amount})"

    def create_agent(self) -> None:
        pass

    def remove_agent(self) -> None:
        pass

    def add_money_to_agent(self) -> None:
        pass

    def remove_money_from_agent(self) -> None:
        pass


class Agent(Person):
    def __init__(
        self,
        full_name: str,
        _id: str,
        super_id: str,
        is_active: bool,
        password: str,
        email: str,
        creation_time: dt.datetime,
        last_edit_time: dt.datetime,
        last_login_time: dt.datetime,
        amount: float,
    ) -> None:
        super().__init__(full_name,_id, super_id, is_active, "agent", password, email, creation_time, last_edit_time, last_login_time, amount)

    def __repr__(self) -> str:
        
        return f"Agent({self._id}, {self.full_name}, {self.super_id}, {self.is_active}, {self.rank}, {'********'}, {self.email}, {self.creation_time}, {self.last_edit_time}, {self.last_login_time}, {self.amount})"

    
        
    def create_user(self) -> None:
        pass

    def remove_user(self) -> None:
        pass

    def add_money_to_user(self) -> None:
        pass

    def remove_money_from_user(self) -> None:
        pass


class User(Person):
    def __init__(
        self,
        full_name: str,
        _id: str,
        super_id: str,
        is_active: bool,
        password: str,
        email: str,
        creation_time: dt.datetime,
        last_edit_time: dt.datetime,
        last_login_time: dt.datetime,
        amount: float,
    ) -> None:
        super().__init__(full_name,_id, super_id, is_active, "user", password, email, creation_time, last_edit_time, last_login_time, amount)

    def __repr__(self) -> str:
        return f"User({self._id}, {self.full_name}, {self.super_id}, {self.is_active}, {self.rank}, {'********'}, {self.email}, {self.creation_time}, {self.last_edit_time}, {self.last_login_time}, {self.amount})"


if __name__ == "__main__":
    now = dt.datetime.now()

    admin = Admin("Alice Smith",Person.generate_id("Alice Smith"), True, "password", "alice@example.com", now, now, now, 1000)
    agent = Agent("Bob Jones",Person.generate_id("Bob Jones"), admin._id, True, "password", "bob@example.com", now, now, now, 1000)
    user  = User("Carol White",Person.generate_id("Carol White"), agent._id, True, "password", "carol@example.com", now, now, now, 1000)

    print(admin)
    print(agent)
    print(user)