import logging

logger = logging.getLogger(__name__)

class ApprovalSystem:
    """
    Prompts the user for approval before sensitive actions
    such as core code modifications, network usage, etc.
    """

    def __init__(self):
        pass

    def request_approval(self, reason: str) -> bool:
        """
        Interact with the user and get a yes/no response.
        """
        logger.info(f"Requesting approval: {reason}")
        print("\n\n" + "="*50)
        print("R&D Approval Required:")
        print(f"Reason: {reason}")
        print("Proceed? (yes/no)")
        print("="*50 + "\n")
        
        while True:
            response = input("> ").strip().lower()
            if response in ['y', 'yes']:
                logger.info("User approved.")
                return True
            elif response in ['n', 'no']:
                logger.info("User denied.")
                return False
            else:
                print("Please enter 'yes' or 'no'.")
