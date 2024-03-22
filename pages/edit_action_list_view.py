import pickle

from PyQt6.QtCore import Qt, QMimeData, QByteArray, QPoint
from PyQt6.QtGui import QDrag
from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QApplication, QStyle

from actions.action_list import ActionUtil
from pages.styled_item_delegate import StyledItemDelegate


class ActionListItem(QListWidgetItem):
    def __init__(self, action_name, action_arg, action_pos, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.action_name = action_name
        self.action_arg = action_arg
        self.action_pos = action_pos
        self.setText(self.action_name)

    def get_action(self):
        action = ActionUtil.get_action_by_name(self.action_name)()
        action.action_pos = self.action_pos
        action.action_arg = self.action_arg
        return action

    @classmethod
    def load(cls, action_list_item_data):
        action_list_view_item = ActionListItem(action_list_item_data["action_name"],
                                               action_list_item_data["action_arg"],
                                               action_list_item_data["action_pos"])
        return action_list_view_item

    def dump(self):
        return {"action_name": self.action_name,
                "action_arg": self.action_arg,
                "action_pos": self.action_pos}


class ActionList(QListWidget):
    my_mime_type = "ActionListView/data_drag"

    def __init__(self, action_items: list[ActionListItem] = None, parent=None):
        super().__init__()
        # 设置列表项之间的间距为 3 像素
        self.ITEM_MARGIN_LEFT = 3
        # 拖动结束时，生成新的的 action
        self.drop_down_action = None
        self.setAcceptDrops(True)
        # 拖动到当前位置对应的元素序号
        self.the_highlighted_row = -2
        self.old_highlighted_row = -2
        # 判断是否正在拖拽
        self.is_drag = False
        self.start_pos = None
        self.the_drag_row = -1
        self.the_selected_row = -1
        self.the_insert_row = 1
        # 不到一半行高：offset() = 19 = 40 / 2 - 1，其中40是行高
        self.offset = 19
        self.init()
        if parent:
            self.setParent(parent)

        if not action_items:
            action_items = []
        for action_item in action_items:
            self.insertItem(action_item.action_pos, action_item)

    @classmethod
    def load(cls, action_list_data):
        action_list_items = [ActionListItem.load(i) for i in action_list_data["action_items"]]
        action_list_view = ActionList(action_list_items)
        return action_list_view

    def dump(self):
        res = []
        # 获取所有 items
        for i in range(self.count()):
            item = self.item(i)
            if not isinstance(item, ActionListItem):
                raise TypeError("item must be an instance of ActionListItem")
            res.append(item.dump())
        return {"action_items": res}

    def init(self):
        # 设置列表项之间的间距为 1 像素
        self.setSpacing(1)
        self.setStyleSheet(
            "QListView{background:rgb(220,220,220); border:0px; margin:0px 0px 0px 0px;}"
            "QListView::Item{height:40px; border:0px; background:rgb(255,255,255);margin-left: "
            + str(self.ITEM_MARGIN_LEFT) + "px;}"
            # "QListView::Item:hover{color:rgba(40, 40, 200, 255); padding-left:14px;}")
                                           "QListView::Item:selected{color:rgb(0, 0, 0);}")
        self.setItemDelegate(StyledItemDelegate())
        # 选中时不出现虚线框
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    # 记录拖拽初始位置
    def mousePressEvent(self, e):
        # 如果在历史事件中左键点击过
        if e.buttons() & Qt.MouseButton.LeftButton:
            self.start_pos = e.pos()

    def mouseReleaseEvent(self, e):
        # 为什么有这段代码？
        if (e.pos() - self.start_pos).manhattanLength() > 5:
            return
        # 鼠标release时才选中
        index = self.indexAt(e.pos())
        self.setCurrentIndex(index)

    def mouseMoveEvent(self, e):
        # 如果在历史事件中左键点击过
        if e.buttons() & Qt.MouseButton.LeftButton:
            # 拖动距离如果太少，直接返回
            if (e.pos() - self.start_pos).manhattanLength() < QApplication.startDragDistance():
                return
            the_drag_index = self.indexAt(self.start_pos)
            self.the_drag_row = the_drag_index.row()
            self.the_selected_row = self.currentIndex().row()
            # 拖拽即选中
            self.setCurrentIndex(the_drag_index)
            the_drag_item = self.item(the_drag_index.row())
            # 拖拽空白处
            if not isinstance(the_drag_item, ActionListItem):
                return
            # 把拖拽数据放在QMimeData容器中
            byte_array = QByteArray(pickle.dumps({"source": "actionList", "data": the_drag_item.dump()}))
            mime_data = QMimeData()
            mime_data.setData(self.my_mime_type, byte_array)
            # 设置拖拽缩略图
            drag = QDrag(self)
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarNormalButton)
            drag.setMimeData(mime_data)
            pixmap = icon.pixmap(10, 10)
            drag.setPixmap(pixmap)
            # 删除的行需要根据theInsertRow和theDragRow的大小关系来判断
            if drag.exec(Qt.DropAction.MoveAction) == Qt.DropAction.MoveAction:
                # 元素向上拖动，会在上面新增一个，因此要删除的位置需要+1
                if self.the_insert_row < self.the_drag_row:
                    the_remove_row = self.the_drag_row + 1
                # 元素向下拖动，会在下面新增一个，因此直接删除即可
                else:
                    the_remove_row = self.the_drag_row
                self.model().removeRow(the_remove_row)

    def dragEnterEvent(self, e):
        source = e.source()
        # 从动作列表中进行拖拽
        if source:
            self.is_drag = True
            e.setDropAction(Qt.DropAction.MoveAction)
            e.accept()

    def dragMoveEvent(self, e):
        # 拖动元素的当前位置不超上边界
        if e.position().y() >= self.offset:
            # 当鼠标移动到两个元素之间时，选中上一个元素
            pos = QPoint()
            pos.setX(int(e.position().x()))
            pos.setY(int(e.position().y()) - self.offset)
            current_index_row = self.indexAt(pos).row()
            # 如果拖动到了没有元素的地方
            if current_index_row == -1:
                last_item = self.item(self.count() - 1)
                last_item_rect = self.visualItemRect(last_item)
                # 如果拖动到了最后一行
                if e.position().y() > last_item_rect.bottomLeft().y():
                    self.the_highlighted_row = self.model().rowCount() - 1
                # 如果拖动到了某item的中间，不显示高亮线
                else:
                    self.the_highlighted_row = -2
            else:
                self.the_highlighted_row = self.indexAt(pos).row()

            # 刷新区域
            self.update(self.model().index(self.the_highlighted_row, 0))
            self.update(self.model().index(self.the_highlighted_row + 1, 0))
            self.the_insert_row = self.the_highlighted_row + 1
        # 插到第一行
        else:
            self.the_highlighted_row = -1
            self.update(self.model().index(0, 0))
            self.update(self.model().index(1, 0))
            self.the_insert_row = 0
        e.setDropAction(Qt.DropAction.MoveAction)
        e.accept()

    def dragLeaveEvent(self, e):
        the_highlighted_row = self.the_highlighted_row
        self.the_highlighted_row = -2
        self.update(self.model().index(the_highlighted_row, 0))
        self.update(self.model().index(the_highlighted_row + 1, 0))
        self.is_drag = False
        self.the_insert_row = -1
        e.accept()

    def dropEvent(self, e):
        self.is_drag = False
        self.the_highlighted_row = -2
        # 向指定行插入数据
        source_data = pickle.loads(e.mimeData().data(self.my_mime_type))
        drop_down_action_item = ActionListItem.load(source_data["data"])
        drop_down_action_item.action_pos = self.the_insert_row
        # 非内部拖动，打开配置窗口，新建动作
        if source_data.get("source") == "functionList":
            # 打开配置页面
            self.drop_down_action = drop_down_action_item.get_action()
            self.drop_down_action.config_page_show()
        # action内部拖动，直接进行替换
        elif source_data.get("source") == "actionList":
            # 如果拖动前位置和拖动后位置相同
            if self.the_insert_row == self.the_drag_row:
                return
            # 如果拖动前位置和拖动后位置相邻
            if self.the_drag_row != -1 and self.the_insert_row == self.the_drag_row + 1:
                return
            self.insert_item(self, self.the_insert_row, drop_down_action_item)
        # 只要拖动过，就取消选中
        self.setCurrentIndex(QListWidget().currentIndex())
        # 已经处理完拖动，设置为None
        e.setDropAction(Qt.DropAction.MoveAction)
        e.accept()

    @staticmethod
    def insert_item(action_list, row, action_item):
        action_list.insertItem(row, action_item)
        if action_item.action_name == "循环执行":
            # 设置带包含的样式
            from pages.include_action_ui import IncludeActionUi
            widget = IncludeActionUi().widget()
            action_item.setSizeHint(widget.size())
            action_list.setItemWidget(action_item, widget)

    def remove(self):
        pass
