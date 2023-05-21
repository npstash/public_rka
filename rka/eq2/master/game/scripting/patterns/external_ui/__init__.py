from rka.components.resources import ResourceBundle


class ExternalBundle(ResourceBundle):
    def __init__(self):
        ResourceBundle.__init__(self, __file__, '.png')
