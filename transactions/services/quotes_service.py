"""
Quotes Service — Daily financial wisdom and motivational quotes.

Provides random or daily-rotated financial quotes to inspire users
on their financial journey.
"""

import logging
from datetime import date
from random import Random
from typing import Dict

logger = logging.getLogger('security')


class QuotesService:
    """
    Manages financial wisdom quotes for daily motivation.

    Quotes are selected either randomly or deterministically based on the
    current date to ensure the same quote appears throughout a day.
    """

    QUOTES = [
        {
            "text": "An investment in knowledge pays the best interest.",
            "author": "Benjamin Franklin",
            "category": "Investment"
        },
        {
            "text": "The best time to plant a tree was 20 years ago. The second best time is now.",
            "author": "Chinese Proverb",
            "category": "Wealth Building"
        },
        {
            "text": "Money is a terrible master but an excellent servant.",
            "author": "P.T. Barnum",
            "category": "Mindset"
        },
        {
            "text": "Wealth consists not in having great possessions, but in having few wants.",
            "author": "Epictetus",
            "category": "Simplicity"
        },
        {
            "text": "The lack of money is the root of all evil.",
            "author": "Mark Twain",
            "category": "Motivation"
        },
        {
            "text": "Opportunity is missed by most because it is dressed in overalls and looks like work.",
            "author": "Thomas Edison",
            "category": "Opportunity"
        },
        {
            "text": "Money moves from those who don't manage it to those who do.",
            "author": "Dave Ramsey",
            "category": "Money Management"
        },
        {
            "text": "The habit of saving is itself an education; it fosters every virtue.",
            "author": "T.T. Munger",
            "category": "Savings"
        },
        {
            "text": "Wealth is the ability to fully experience life.",
            "author": "Henry David Thoreau",
            "category": "Quality of Life"
        },
        {
            "text": "Your wealth is a result of your daily habits, not your education.",
            "author": "Unknown",
            "category": "Habits"
        },
        {
            "text": "The more you learn, the more you earn.",
            "author": "Warren Buffett",
            "category": "Education"
        },
        {
            "text": "Don't be afraid to give up the good to go for the great.",
            "author": "John D. Rockefeller",
            "category": "Ambition"
        },
        {
            "text": "Wealth is not about having a lot of money; it's about having a lot of options.",
            "author": "Chris Rock",
            "category": "Freedom"
        },
        {
            "text": "The secret of getting rich is: do it. The secret of staying rich is: discipline.",
            "author": "Unknown",
            "category": "Discipline"
        },
        {
            "text": "Every dollar you own is a slave working for you if you use it right.",
            "author": "J. Paul Getty",
            "category": "Capital"
        },
        {
            "text": "Budgeting doesn't limit your freedom; it guarantees it.",
            "author": "Dave Ramsey",
            "category": "Budgeting"
        },
        {
            "text": "The greatest wealth is a healthy body and a peaceful mind.",
            "author": "Unknown",
            "category": "Wellbeing"
        },
        {
            "text": "Spend less than you earn, and you will always be rich.",
            "author": "Unknown",
            "category": "Saving"
        },
        {
            "text": "Your net worth to the world is usually determined by what remains after your bad habits are subtracted from your good ones.",
            "author": "Benjamin Franklin",
            "category": "Character"
        },
        {
            "text": "It's not how much money you make, but how much you keep.",
            "author": "Robert Kiyosaki",
            "category": "Money Management"
        },
    ]

    @classmethod
    def get_daily_quote(cls) -> Dict:
        """
        Get the 'quote of the day' — deterministic based on current date.

        The same quote will be returned for all users on the same day,
        ensuring a unified motivational message across the day.

        Returns:
            dict with 'text', 'author', 'category', and 'date' keys.
        """
        today = date.today()
        # Use day-of-year as seed for deterministic selection
        rng = Random(today.toordinal())
        quote = rng.choice(cls.QUOTES)

        return {
            "text": quote["text"],
            "author": quote["author"],
            "category": quote["category"],
            "date": str(today),
            "type": "daily"
        }

    @classmethod
    def get_random_quote(cls) -> Dict:
        """
        Get a random quote from the collection.

        Returns:
            dict with 'text', 'author', and 'category' keys.
        """
        from random import choice
        quote = choice(cls.QUOTES)

        return {
            "text": quote["text"],
            "author": quote["author"],
            "category": quote["category"],
            "type": "random"
        }

    @classmethod
    def get_all_quotes(cls) -> Dict:
        """
        Get all available quotes.

        Useful for frontend caching or displaying a collection.

        Returns:
            dict with 'count' and 'quotes' list.
        """
        return {
            "count": len(cls.QUOTES),
            "quotes": cls.QUOTES
        }
