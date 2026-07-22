import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class MovementController:
    '''
    This is a basic application controller backend for the `qdlmove` application.
    In its current implementation, it manages calls to move or step the various 
    hardware by reference to their name as stored in the `self.positioners` dict.
    
    In the future, if more features are desired of the `qdlmove` application, 
    for example recording/saving of positions, plotting points, etc. the developer
    should add these features into this class and update the GUI/main application
    to trigger methods or store data in this class.
    '''
    def __init__(self, positioners: dict = {}):
        self.positioners = positioners # dictionary of the controller instantiations
        self.busy = False


    def move_axis(self, axis_controller_name: str, position: float):
        if self.busy:
            logger.warning('Movement controller busy')
            return None
        self.busy = True
        # Move the axis specified by the axis_controller_name
        self.positioners[axis_controller_name].go_to_position(position)
        self.busy = False

    def step_axis(self, axis_controller_name: str, dx: float):
        if self.busy:
            logger.warning('Movement controller busy')
            return None
        self.busy = True
        # Step the axis specified by the axis_controller_name
        self.positioners[axis_controller_name].step_position(dx)
        self.busy = False