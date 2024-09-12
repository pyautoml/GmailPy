# https://github.com/pyautoml/GmailPy

from string import Template


"""
This module contains several pre-defined email templates, each represented by a Template object from the string module. 
These templates can be used to generate personalized email content based on specific variables.

Usage example:

    recipient_name = "John Doe"
    emails_sent = 10
    emails_received = 5
    spam = 2
    topics = ["Project Updates", "Meeting Reminders", "Feedback"]
    assistant_name = "Email Assistant"

    email_content = emails_sumup_template.substitute(
        recipient_name=recipient_name,
        emails_sent=emails_sent,
        emails_received=emails_received,
        spam=spam,
        topics=", ".join(topics),
        assistant_name=assistant_name,
    )

    print(email_content)
"""


emails_sumup_template = Template("""
Hi ${recipient_name},

Here's a summary of your mailbox content for the last week:

- Emails sent: ${emails_sent}
- Emails received: ${emails_received}
- Spam ${spam}
- Topics: ${topics}

Have a great weekend!

Best regards,
${assistant}
""")


holiday_template = Template("""
Hello,

Thank you for your email. I am currently out of the office for the ${holiday_name} holiday from ${start_date} to ${end_date}.
I will have limited access to email during this time.

Best wishes,
${your_name}
""")

assistant_template = Template("""
Dear ${user_name},

I'm your new AI-powered email assistant. I'm here to help you manage your inbox more efficiently. Here are some ways I can assist you:

1. Summarize long email threads
2. Draft responses to common inquiries
3. Categorize and prioritize your emails
4. Set reminders for important follow-ups

To get started, simply reply to this email with "Help" for more information.

Best regards,
Your Personal Assistant
""")


meeting_request_template = Template("""
Dear ${recipient_name},

I hope this email finds you well. I would like to schedule a meeting to discuss ${meeting_subject}.

Proposed date and time: ${proposed_datetime}
Duration: ${duration}
Location/Platform: ${location}

Please let me know if this works for you or suggest an alternative time that suits your schedule.
Looking forward to our discussion.

Best regards,
${your_name}
""")

newsletter_template = Template("""
Dear ${subscriber_name},

Welcome to our ${month_year} newsletter! Here are the highlights:

1. ${highlight_1}
2. ${highlight_2}
3. ${highlight_3}

${main_content}

We hope you found this newsletter informative. If you have any questions or feedback, please don't hesitate to reach out.
Thank you for your continued support!

Best regards,
The ${company_name} Team
""")