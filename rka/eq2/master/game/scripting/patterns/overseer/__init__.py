from rka.components.resources import ResourceBundle


class OverseerBundle(ResourceBundle):
    def __init__(self):
        ResourceBundle.__init__(self, __file__, '.png')
