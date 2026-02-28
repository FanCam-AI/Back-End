from models import Result
from domain.schema import UserCreate
from sqlalchemy import desc
from passlib.context import CryptContext
from datetime import datetime
from sqlalchemy.orm import Session
from models import User
from fastapi.responses import HTMLResponse

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_result_list_by_user_id(db: Session, user_id: int):
    return db.query(Result) \
        .filter(Result.user_id == user_id) \
        .order_by(desc(Result.id)) \
        .all()


def get_result_list(db: Session):
    result_list = db.query(Result)\
        .order_by(Result.create_date.desc())\
        .all()
    return result_list


def save_result(db: Session,title, file_path, file_type, current_user_id):
    result = Result(
        title=title,
        file_path=file_path,
        file_type=file_type,
        create_date=datetime.now(),
        user_id=current_user_id
    )

    db.add(result)
    db.commit()
    db.refresh(result)

    return True




def create_user(db: Session, user_create: UserCreate):
    db_user = User(username=user_create.username,
                   email=user_create.email,
                   create_count=user_create.create_count,
                   apple_refresh_token=user_create.apple_refresh_token)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def get_existing_user(db: Session, user_create: UserCreate):
    return db.query(User).filter(
        (User.username == user_create.username) |
        (User.email == user_create.email)
    ).first()


def get_user(db: Session, user_id: str):
    return db.query(User).filter(User.id == user_id).first()



def save_refresh_token(db: Session, username: str, refresh_token: str):
    user = db.query(User).filter(User.username == username).first()
    if user:
        user.refresh_token = refresh_token
        db.commit()



def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()


def password_form(error_message: str = ""):
    return HTMLResponse(f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background-color: #f9f9f9;
                    color: #111;
                }}
                .container {{
                    background: #fff;
                    padding: 2.5rem 2rem;
                    border-radius: 16px;
                    box-shadow: 0 6px 24px rgba(0,0,0,0.12);
                    text-align: center;
                    max-width: 360px;
                    width: 90%;
                    border: 1px solid #e5e5e5;
                    animation: fadeIn 0.5s ease-in-out;
                }}
                h3 {{
                    margin-bottom: 1.5rem;
                    font-size: 1.3rem;
                    font-weight: 600;
                    color: #000;
                }}
                .error {{
                    color: red;
                    margin-bottom: 1rem;
                    font-size: 0.95rem;
                }}
                input[type="password"] {{
                    padding: 0.75rem 1rem;
                    border-radius: 10px;
                    border: 1px solid #ccc;
                    margin-bottom: 1.2rem;
                    width: 100%;
                    max-width: 260px;
                    font-size: 1rem;
                    transition: border-color 0.2s, box-shadow 0.2s;
                }}
                input[type="password"]:focus {{
                    outline: none;
                    border-color: #000;
                    box-shadow: 0 0 0 2px rgba(0,0,0,0.1);
                }}
                button {{
                    padding: 0.75rem 1.5rem;
                    border-radius: 10px;
                    border: none;
                    background-color: #000;
                    color: #fff;
                    font-size: 1rem;
                    font-weight: 600;
                    cursor: pointer;
                    transition: background-color 0.3s, transform 0.2s;
                }}
                button:hover {{
                    background-color: #333;
                    transform: translateY(-2px);
                }}
                @keyframes fadeIn {{
                    from {{ opacity: 0; transform: translateY(20px); }}
                    to {{ opacity: 1; transform: translateY(0); }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h3>🔒 Enter password to view the file</h3>
                {"<div class='error'>" + error_message + "</div>" if error_message else ""}
                <form action="" method="post">
                    <input type="password" name="password" placeholder="Password" required/>
                    <br/>
                    <button type="submit">Submit</button>
                </form>
            </div>
        </body>
        </html>
    """)



def file_not_found_form(error_message: str = ""):
    return HTMLResponse(f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background-color: #f9f9f9;
                    color: #111;
                }}
                .container {{
                    background: #fff;
                    padding: 2.5rem 2rem;
                    border-radius: 16px;
                    box-shadow: 0 6px 24px rgba(0,0,0,0.12);
                    text-align: center;
                    max-width: 360px;
                    width: 90%;
                    border: 1px solid #e5e5e5;
                    animation: fadeIn 0.5s ease-in-out;
                }}
                h3 {{
                    margin-bottom: 1.5rem;
                    font-size: 1.3rem;
                    font-weight: 600;
                    color: #000;
                }}
                .error {{
                    color: red;
                    margin-bottom: 1rem;
                    font-size: 0.95rem;
                }}
                input[type="password"] {{
                    padding: 0.75rem 1rem;
                    border-radius: 10px;
                    border: 1px solid #ccc;
                    margin-bottom: 1.2rem;
                    width: 100%;
                    max-width: 260px;
                    font-size: 1rem;
                    transition: border-color 0.2s, box-shadow 0.2s;
                }}
                input[type="password"]:focus {{
                    outline: none;
                    border-color: #000;
                    box-shadow: 0 0 0 2px rgba(0,0,0,0.1);
                }}
                button {{
                    padding: 0.75rem 1.5rem;
                    border-radius: 10px;
                    border: none;
                    background-color: #000;
                    color: #fff;
                    font-size: 1rem;
                    font-weight: 600;
                    cursor: pointer;
                    transition: background-color 0.3s, transform 0.2s;
                }}
                button:hover {{
                    background-color: #333;
                    transform: translateY(-2px);
                }}
                @keyframes fadeIn {{
                    from {{ opacity: 0; transform: translateY(20px); }}
                    to {{ opacity: 1; transform: translateY(0); }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h3>File Not Found. Please enter the correct address again.</h3>
                {"<div class='error'>" + error_message + "</div>" if error_message else ""}
            </div>
        </body>
        </html>
    """)