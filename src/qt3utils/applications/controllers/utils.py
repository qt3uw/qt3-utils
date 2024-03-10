import logging
import threading
import tkinter as tk
from tkinter import ttk
from typing import Any, List, Tuple, Type, Union, Literal, Sequence, Callable

_DEFAULT_PADX = 10
_DEFAULT_WIDGET_WIDTH = 10
_DEFAULT_COLUMN_1_SIZE = 180
_DEFAULT_COLUMN_2_SIZE = 140
_DEFAULT_POPUP_WINDOW_WIDTH = 300
_DEFAULT_POPUP_WINDOW_HEIGHT = 100


def make_tab_view(
        parent: Union[tk.Toplevel, ttk.Widget],
        tab_padx: int = _DEFAULT_PADX,
        tab_pady: int = _DEFAULT_PADX,
        tab_sticky: str = tk.NSEW,
        tab_row: int = 0,
        tab_column: int = 0,
        tab_columnspan: int = 2,
        tab_rowspan: int = 1,
        tab_ipadx: int = 0,
        tab_ipady: int = 0,
) -> ttk.Notebook:
    """
    This helper method creates a tab view.

    Parameters
    ----------
    parent: Union[tk.Toplevel, ttk.Widget]
        The parent window the tab view will be inserted in.
    tab_padx: int
        The padding of the tabs.
    tab_pady: int
        The padding of the tabs.
    tab_sticky: str
        The sticky of the tabs.
    tab_row: int
        The row of the tab view in the window.
    tab_column: int
        The column of the tab view in the window.
    tab_columnspan: int
        The column span of the tab view in the window.
    tab_rowspan: int
        The row span of the tab view in the window.
    tab_ipadx: int
        The internal padding of the tab view in the window.
    tab_ipady: int
        The internal padding of the tab view in the window.

    Returns
    -------
    ttk.Notebook
        The generated tab view.
    """
    tab_view = ttk.Notebook(parent)
    tab_view.grid(
        row=tab_row, column=tab_column, padx=tab_padx, pady=tab_pady,
        columnspan=tab_columnspan, rowspan=tab_rowspan,
        sticky=tab_sticky,
        ipadx=tab_ipadx, ipady=tab_ipady,
    )

    return tab_view


def make_label_frame(
        parent: Union[tk.Toplevel, ttk.Widget, ttk.Frame],
        label_text: str,
        row: int,
        padx: int = _DEFAULT_PADX,
        pady: int = 5,
        column_span: int = 2,
        column_minsizes: List[int] = None,
        sticky: str = '',
):
    """
    This helper method creates a label frame.

    Parameters
    ----------
    parent: Union[tk.Toplevel, ttk.Widget]
        The parent window the label frame will be inserted in.
    label_text: str
        The text of the label.
    row: int
        The row of label frame in the window.
    padx: int
        The x padding of the label frame.
    pady: int
        The y padding of the label frame.
    column_span: int
        The label_frame_column_span. Default is 2.
    column_minsizes: List[int]
        A list of minimum sizes of columns in range(len(column_minsizes)).
    sticky: str


    Returns
    -------
    ttk.LabelFrame
        The generated label frame
    """
    if column_minsizes is None:
        column_minsizes = [_DEFAULT_COLUMN_1_SIZE, _DEFAULT_COLUMN_2_SIZE]

    label_frame = ttk.LabelFrame(parent, text=label_text)
    label_frame.grid(row=row, column=0, padx=padx, pady=pady, columnspan=column_span, sticky=sticky)
    for i in range(len(column_minsizes)):
        label_frame.columnconfigure(i, minsize=column_minsizes[i])
    return label_frame


def make_label_and_entry(
        parent: Union[tk.Toplevel, ttk.Widget],
        label_text: str,
        row: int,
        value: Any,
        variable_class: Type[tk.Variable],
        label_padx: int = _DEFAULT_PADX,
        entry_width: int = _DEFAULT_WIDGET_WIDTH
) -> Tuple[ttk.Label, ttk.Entry, tk.Variable]:
    """
    This helper method creates a row of the label-entry tk widgets.

    Parameters
    ----------
    parent: Union[tk.Toplevel, ttk.Widget]
        The parent window the label-entry will be inserted in.
    label_text: str
        The text of the label.
    row: int
        The row of label-entry in the window.
    value: Any
        The initial value of the entry.
        Must be the same type as the `variable_class` supported type.
    variable_class: Type[ttk.Variable]
        The variable class of the text variable connected to the entry.
        Examples: tk.DoubleVar, tk.IntVar, tk.BoolVar, or tk.StringVar.
    label_padx: int
        The padding of the label.
    entry_width: int
        The width of the entry.

    Returns
    -------
    Tuple[ttk.Label, ttk.Entry, tk.Variable]
        The generated label, entry and variable
    """
    label = ttk.Label(parent, text=label_text)
    label.grid(row=row, column=0, padx=label_padx)

    variable = variable_class(value=value)

    entry = ttk.Entry(parent, textvariable=variable, width=entry_width)
    # entry.grid(row=row, column=1, sticky=ttk.NSEW)
    entry.grid(row=row, column=1)

    return label, entry, variable


def make_label_and_option_menu(
        parent: Union[tk.Toplevel, ttk.Widget],
        label_text: str,
        row: int,
        option_list: Sequence[str],
        value: str,
        label_padx: int = _DEFAULT_PADX,
        option_menu_width: int = _DEFAULT_WIDGET_WIDTH,
) -> Tuple[ttk.Label, ttk.OptionMenu, tk.Variable]:
    """
    This helper method creates a row of the label-option menu tk widgets.

    Parameters
    ----------
    parent: Union[tk.Toplevel, ttk.Widget]
        The parent window the label-option menu will be inserted in.
    label_text: str
        The text of the label.
    row: int
        The row of label-option menu in the window.
    value: str
        The initial value of the option menu.
    option_list: Sequence[str]
        The list of options in the option menu.
    label_padx: int
        The padding of the label.
    option_menu_width: int
        The widnth of the option menu.

    Returns
    -------
    Tuple[ttk.Label, ttk.OptionMenu, tk.Variable]
        The generated label, option menu and variable
    """
    label = ttk.Label(parent, text=label_text)
    label.grid(row=row, column=0, padx=label_padx)

    variable = tk.StringVar(value=value)

    option_menu = ttk.OptionMenu(parent, variable, value, *option_list)
    option_menu.grid(row=row, column=1)

    return label, option_menu, variable


def make_label_and_check_button(
        parent: Union[tk.Toplevel, ttk.Widget],
        label_text: str,
        row: int,
        value: bool,
        label_padx: int = _DEFAULT_PADX,
) -> Tuple[ttk.Label, ttk.Checkbutton, tk.BooleanVar]:
    """
    This helper method creates a row of the label-check button tk widgets.

    Parameters
    ----------
    parent: Union[tk.Toplevel, ttk.Widget]
        The parent window the label-check button will be inserted in.
    label_text: str
        The text of the label.
    row: int
        The row of label-check button in the window.
    value: bool
        The initial value of the check button.
    label_padx: int
        The padding of the label. Default is 10.

    Returns
    -------
    Tuple[ttk.Label, ttk.Checkbutton, tk.BoolVar]
        The generated label, checkbutton and variable.
    """
    label = ttk.Label(parent, text=label_text)
    label.grid(row=row, column=0, padx=label_padx)

    variable = tk.BooleanVar(value=value)

    tick_button = ttk.Checkbutton(parent, variable=variable)
    tick_button.grid(row=row, column=1)

    return label, tick_button, variable


def make_separator(
        parent: Union[tk.Toplevel, ttk.Widget],
        row: int,
        orient: Literal['horizontal', 'vertical'] = tk.HORIZONTAL,
        column: int = 0,
        column_span: int = 2,
        padx: int = 10,
        pady: int = 5,
        sticky: str = tk.EW,
) -> ttk.Separator:
    """
    This helper method creates a separator.

    Parameters
    ----------
    parent: Union[tk.Toplevel, ttk.Widget]
        The parent window the separator will be inserted in.
    row: int
        The row of separator in the window.
    orient: Literal['horizontal', 'vertical']
        The orientation of the separator. Default is 'horizontal'.
    column: int
        The column of separator in the window. Default is 0.
    column_span: int
        The column span of separator in the window. Default is 2.
    padx: int
        The padding of the separator in the x direction. Default is 10.
    pady: int
        The padding of the separator in the y direction. Default is 5.
    sticky: str
        The sticky direction of the separator. Default is 'EW'.

    Returns
    -------
    ttk.Separator
        The generated separator.
    """
    separator = ttk.Separator(parent, orient=orient)
    separator.grid(row=row, column=column, columnspan=column_span, sticky=sticky, padx=padx, pady=pady)

    return separator


def prepare_list_for_option_menu(list_to_prepare: Sequence[Any], filler_value: str = 'None') -> List[str]:
    """
    This helper method prepares a list for the option menu.

    Parameters
    ----------
    list_to_prepare: Sequence[Any]
        The list to prepare.
    filler_value: str
        This value will be added to the returned list if the list is empty.

    Returns
    -------
    List[str]
        The prepared list.
    """
    return [str(element) for element in list_to_prepare] if len(list_to_prepare) > 0 else [filler_value]


def make_popup_window_and_take_threaded_action(
        parent: Union[tk.Toplevel, ttk.Widget, ttk.Frame, tk.Tk, None],
        title: str,
        message: str,
        action: Callable[[], Any],
        width: int = _DEFAULT_POPUP_WINDOW_WIDTH,
        height: int = _DEFAULT_POPUP_WINDOW_HEIGHT,
        end_event: threading.Event = None,
        logger: logging.Logger = None,
):
    """
    This helper method creates a popup window with a message,
    and takes a threaded action within the popup window.
    The popup window will be destroyed after the action is
    completed.
    If an error occurs, then an exception is raised and registered
    if a logger is provided.
    This ensures that the thread closes normally either way.

    Parameters
    ----------
    parent: Union[tk.Toplevel, ttk.Widget]
        The parent window the popup window will be inserted in.
    title: str
        The title of the popup window.
    message: str
        The message of the popup window.
    action: Callable[[], None]
        The method to call within the thread.
    width: int
        The width of the popup window. Default is 300.
    height: int
        The height of the popup window. Default is 100.
    end_event: threading.Event
        The event to set when the action is completed.
        Default is None. If None, there will be no
        indication the thread is finished.
    logger: logging.Logger
        If not None, the logger will send a warning
        if an error occurs during the given action.
    """
    popup_window = tk.Toplevel(parent, )
    popup_window.attributes('-disabled', True)  # disables interaction with everything in the popup
    popup_window.grab_set()  # prevents other windows from being accessed while the popup window is open
    popup_window.title(title)

    message_label = ttk.Label(popup_window, text=message)
    message_label.pack(expand=True)

    if parent is not None:
        x = parent.winfo_x() + parent.winfo_width() // 2 - width // 2
        y = parent.winfo_y() + parent.winfo_height() // 2 - height // 2
        popup_window.geometry(f'{width}x{height}+{x}+{y}')
    else:
        popup_window.geometry(f'{width}x{height}')
    popup_window.resizable(False, False)

    def thread_target():
        try:
            action()
        except Exception as e:
            if logger:
                logger.warning(f'Error in threaded action behind popup window: {e}')
        if end_event:
            end_event.set()
        popup_window.destroy()

    thread = threading.Thread(target=thread_target)
    thread.start()

    popup_window.update()
