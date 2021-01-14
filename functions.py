from flask import session, redirect
from functools import wraps
from datetime import date, timedelta, datetime


def check(text):
    """Check whether password checks requirements."""

    has_digit = has_lower = has_upper = False

    for char in text:
        if char.isdigit():
            has_digit = True
        elif char.islower():
            has_lower = True
        elif char.isupper():
            has_upper = True

    if has_digit == has_lower == has_upper == True:
        return True

    return False


def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/1.0/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def end_of_month(date):
    """ Compute last day of the month."""

    if date.month == 12:
        return date.replace(day=31)
    return date.replace(month=date.month+1, day=1) - timedelta(days=1)


def check_plan(x):
    """Check if a plan exists."""
    if len(x) != 0:
        return True
    return False