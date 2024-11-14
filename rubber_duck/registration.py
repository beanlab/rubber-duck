from quest import step


class RegistrationWorkflow:
    def __init__(self,
                 send_message,
                 fetch_message
                 ):
        self._send_message = step(send_message)
        self._fetch_message = step(fetch_message)


