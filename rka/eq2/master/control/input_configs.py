from rka.components.ui.capture import Rect
from rka.eq2.master.control import InputConfig
from rka.eq2.master.control.input_config import InputConfigDelegate
from rka.eq2.master.control.input_templates import Hotbar1_Common, Hotbar2_Mouse_1280, Hotbar3_Mouse_1280, Hotbar4_Common, Hotbar5_Mouse_1280, HotbarUp2_Mouse_1280, \
    Keyboard_Common, Hotbar2_Mouse_1920, Hotbar3_Mouse_1920, Hotbar5_Mouse_1920, HotbarUp2_Mouse_1920, SpecialActions_Common, CraftingHotbar_Common
from rka.eq2.shared.host import HostRole, InputType


class InputConfig1280(InputConfigDelegate):
    def __init__(self, host_role: HostRole):
        assert host_role == HostRole.Slave
        InputConfigDelegate.__init__(self)
        self.hotbar1 = Hotbar1_Common(self.delegates)
        self.hotbar2 = Hotbar2_Mouse_1280(self.delegates)
        self.hotbar3 = Hotbar3_Mouse_1280(self.delegates)
        self.hotbar4 = Hotbar4_Common(self.delegates)
        self.hotbar5 = Hotbar5_Mouse_1280(self.delegates)
        self.hotbarUp11 = None
        self.hotbarUp12 = HotbarUp2_Mouse_1280(self.delegates)
        self.crafting_hotbar = CraftingHotbar_Common(self.delegates)
        self.keyboard = Keyboard_Common(self.delegates)
        self.special = SpecialActions_Common(self.delegates, host_role)
        self.screen.X = 8
        self.screen.Y = 1
        self.screen.W = 1040
        self.screen.H = 800
        self.screen.VP_W_center = 520
        self.screen.VP_H_center = 340
        self.screen.bags_item_1 = [(35, 130), (335, 130), (514, 130), (695, 130), (876, 130), None]
        self.screen.bags_width = [6, 4, 4, 4, 4, None]
        self.screen.bag_slot_size = 43
        self.screen.detrim_list_window = Rect(277, 578, 277 + (25 * 6), 578 + 25)
        self.screen.detrim_count_window = Rect(270, 530, 430, 570)
        self.screen.target_buff_window = Rect(617, 565, 778, 615)
        self.screen.target_casting_bar = Rect(631 - 5, 542 - 5, 766 + 5, 553 + 5)


class InputConfig1920(InputConfigDelegate):
    def __init__(self, host_role: HostRole):
        InputConfigDelegate.__init__(self)
        self.hotbar1 = Hotbar1_Common(self.delegates)
        self.hotbar2 = Hotbar2_Mouse_1920(self.delegates)
        self.hotbar3 = Hotbar3_Mouse_1920(self.delegates)
        self.hotbar4 = Hotbar4_Common(self.delegates)
        self.hotbar5 = Hotbar5_Mouse_1920(self.delegates)
        self.hotbarUp11 = None
        self.hotbarUp12 = HotbarUp2_Mouse_1920(self.delegates)
        self.crafting_hotbar = CraftingHotbar_Common(self.delegates)
        self.keyboard = Keyboard_Common(self.delegates)
        self.special = SpecialActions_Common(self.delegates, host_role)
        self.screen.X = 8
        self.screen.Y = 8
        self.screen.W = 1840
        self.screen.H = 1080
        self.screen.VP_W_center = 960
        self.screen.VP_H_center = 510
        self.screen.bags_item_1 = [(260, 150), (36, 150), (602, 150), (1067, 150), (1331, 150), (1597, 150)]
        self.screen.bags_width = [5, 5, 6, 6, 6, 6]
        self.screen.bag_slot_size = 43
        self.screen.detrim_list_window = Rect(667, 895, 667 + (25 * 6), 895 + 25)
        self.screen.detrim_count_window = Rect(670, 830, 830, 870)
        self.screen.target_buff_window = Rect(1021, 865, 1185, 917)
        self.screen.target_casting_bar = Rect(1036 - 5, 842 - 5, 1171 + 5, 853 + 5)


class InputConfigFactory:
    @staticmethod
    def get_input_config(host_role: HostRole, input_type: InputType) -> InputConfig:
        if input_type == InputType.CONFIG_1920:
            return InputConfig1920(host_role)
        elif input_type == InputType.CONFIG_1280:
            return InputConfig1280(host_role)
        assert False
