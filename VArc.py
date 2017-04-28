import random
import subprocess
import sys
import os
import xml.etree.ElementTree as elTree
from threading import Timer

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QApplication, QGraphicsScene, QGraphicsView)
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent, QSoundEffect, QMediaPlaylist
from PyQt5.QtMultimediaWidgets import QGraphicsVideoItem
from PyQt5.QtGui import QPixmap, QMovie, QCursor, QFont
from PyQt5.QtCore import (Qt, QUrl, QSizeF, QSize, QPropertyAnimation, QPoint,
                          QParallelAnimationGroup, QEasingCurve, QAbstractAnimation)


class Game:
    def __init__(self, name: str, display: str, emu_info=None, game_type="Arcade"):
        self.name = name
        self.display = display
        self.emu_info = emu_info
        self.game_type = game_type

    def __cmp__(self, other):
        if isinstance(other, Game):
            if self.display > other.display:
                return 1
            elif self.display < other.display:
                return -1
            else:
                return 0

    def __lt__(self, other):
        if isinstance(other, Game):
            if self.display < other.display:
                return True
            else:
                return False

    def __gt__(self, other):
        if isinstance(other, Game):
            if self.display > other.display:
                return True
            else:
                return False
    
    def __eq__(self, other):
        if isinstance(other, Game):
            if self.display == other.display:
                return True
            else:
                return False


v_player = None  # These globals are probably a bad idea
bgm = None
cur_game = None
top_pos = QPoint()
bot_pos = QPoint()
wheel_anims = None
center = None

# These defaults are overridden by config.xml, if the values are present
config = {'rom_path': 'ROM/', 'exe_path': 'shortcuts/', 'image_path': 'image/', 'preview_path': 'video/',
          'mame_exec': 'mame/mame.exe', 'audio_path': 'audio/', 'gif_bg': 'True', 'flip_scrolling': 'False'}


def read_conf():
    root = elTree.parse('config.xml').getroot()
    for entry in root:
        key = entry.find('key').text
        try:
            config[key] = entry.find('value').text
        except KeyError:
            print('Invalid config: ' + entry.find('value').text)


class VArcMain(QWidget):
    def __init__(self):
        global bgm, wheel_anims

        super().__init__()
        # Controls
        self.up = []
        self.down = []
        self.left = []
        self.right = []
        self.select = []

        self.labels = []

        # Wheel/Game List
        self.wheel = None
        self.center = None
        self.splash = None
        wheel_anims = QParallelAnimationGroup()
        self.games = populate_games()

        # Media
        self.click = QSoundEffect()
        self.click.setSource(QUrl.fromLocalFile(config['audio_path'] + 'wheelSFX.wav'))
        bgm = QMediaPlayer(self)
        bgm.setMedia(QMediaContent(QUrl.fromLocalFile(config['audio_path'] + 'bgm.mp3')))
        bgm.setVolume(30)
        bgm.play()

        # Startup
        read_conf()
        self.read_keys()

        if config['flip_scrolling'] == 'True':
            self.up, self.down = self.down, self.up

        self.init_ui()

    def init_ui(self):
        global v_player, cur_game, config, top_pos, bot_pos, wheel_anims

        backgrounds = []
        for file in os.listdir(config['image_path'] + 'background/'):
            if config['gif_bg'] == 'True':
                if file.endswith(".gif"):
                    backgrounds.append(file)
            elif file.endswith(('.png', '.jpg')):
                backgrounds.append(file)

        bg_mov = QMovie(config['image_path'] + 'background/' + random.choice(backgrounds))
        bg_mov.setScaledSize(QSize(1920, 1080))
        bg = QLabel(self)

        bg.setMovie(bg_mov)
        bg_mov.start()
        h_box = QHBoxLayout(bg)
        v_box = QVBoxLayout(bg)
        self.wheel = v_box
        h_box.addLayout(v_box)
        h_box.addStretch(1)

        v_player = VideoPlayer(640, 480)
        v_player.setFixedSize(640, 480)
        v_player.setEnabled(0)

        self.splash = QLabel()
        v_container = QVBoxLayout()
        v_container.addStretch(1)
        v_container.addWidget(self.splash, alignment=Qt.AlignCenter)
        v_container.addWidget(v_player, alignment=Qt.AlignAbsolute)
        v_container.addStretch(1)
        h_box.addLayout(v_container)
        h_box.addStretch(1)

        w_labels = []
        for a, x in enumerate(self.games):
            lbl = QLabel(self)
            lbl.hide()
            lbl.setFixedSize(400, 175)
            self.labels.append(lbl)
            if a < 5:
                if a == 2:
                    cur_game = [x, 2]
                    self.center = lbl
                    self.splash.setStyleSheet('color: white; font-size: 24pt;')
                    self.splash.setText(x.display + ' - ' + x.emu_info)
                    v_player.load(x.name + '.mp4')
                    v_player.play()
                lbl.show()
                v_box.addWidget(lbl)
                lbl.setFocus()

            w_label = QLabel(self)
            anim = WheelAnimation(w_label, b'pos', lbl)
            w_labels.append((w_label, lbl))
            wheel_anims.addAnimation(anim)

            anim.setEasingCurve(QEasingCurve.OutQuad)
            anim.setDuration(100)

            if os.path.isfile(config['image_path'] + x.name + '.png'):
                w_label.setPixmap(QPixmap(config['image_path'] + x.name + '.png')
                                  .scaled(400, 175, Qt.IgnoreAspectRatio))
            else:
                w_label.setStyleSheet('color: white; font-size 36pt;')
                w_label.setText(x.display)

        self.setWindowTitle('VArc')
        self.showFullScreen()

        top_pos = QPoint(10, -400)
        bot_pos = QPoint(10, 1480)

        for a in w_labels:
            pos = a[1].pos()
            if pos.x() is not 0:
                if a[1] == self.center:
                    a[0].move(pos.x() + 30, pos.y())
                else:
                    a[0].move(pos)

            else:
                a[0].hide()

    def keyPressEvent(self, e):
        if e.key() in self.down:
            self.move_wheel(False)
            try_preview()
        elif e.key() in self.up:
            self.move_wheel(True)
            try_preview()
        elif e.key() in self.select:
            start_game()
        elif e.key() in self.left:
            print('Going left!')
        elif e.key() in self.right:
            print('Going right!')

    def move_wheel(self, up: bool):
        global cur_game
        self.click.play()
        layout = self.wheel
        if up:
            to_show = self.labels[5]
            to_show.show()
            to_remove = layout.itemAt(0).widget()
            to_remove.hide()
            layout.removeWidget(to_remove)
            layout.addWidget(to_show)
            self.labels.append(self.labels.pop(0))
            cur_game[1] = (cur_game[1] + 1) % len(self.games)
            cur_game[0] = self.games[cur_game[1]]
            self.center = layout.itemAt(3).widget()

        else:
            to_show = self.labels.pop()
            to_show.show()
            to_remove = layout.itemAt(4).widget()
            to_remove.hide()
            layout.removeWidget(to_remove)
            layout.insertWidget(0, to_show)
            self.labels.insert(0, to_show)
            cur_game[1] = (cur_game[1] - 1) % len(self.games)
            cur_game[0] = self.games[cur_game[1]]
        self.center = layout.itemAt(2).widget()

        QApplication.instance().processEvents()
        self.anim_wheel(up)

        self.splash.setText(cur_game[0].display + ' - ' + cur_game[0].emu_info)
        self.center.resize(self.center.width() + 2000, self.center.height() + 2000)

    def anim_wheel(self, up: bool):
        global top_pos, bot_pos, wheel_anims
        for a in range(wheel_anims.animationCount()):
            anim = wheel_anims.animationAt(a)

            if anim.shadow_lbl.isVisible():
                pos = anim.shadow_lbl.pos()
                if anim.shadow_lbl == self.center:
                    pos.setX(pos.x() + 120)
                anim.targetObject().show()
                anim.setDuration(100)
                anim.setEndValue(pos)
            else:
                anim.targetObject().hide()
                if up:
                    anim.setEndValue(bot_pos)
                    anim.setDuration(0)
                    anim.targetObject().move(bot_pos)
                else:
                    anim.setEndValue(top_pos)
                    anim.setDuration(0)
                    anim.targetObject().move(top_pos)

        wheel_anims.start(QAbstractAnimation.KeepWhenStopped)

    def read_keys(self):
        root = elTree.parse('keybinds.xml').getroot()
        for bind in root:
            key = bind.find('key').text
            try:
                value = eval('Qt.' + bind.find('value').text)
            except AttributeError:
                print('Invalid keybind: ' + bind.find('value').text)
                value = None
            if value is not None:
                if key == 'Up':
                    self.up.append(value)
                elif key == 'Down':
                    self.down.append(value)
                elif key == 'Left':
                    self.left.append(value)
                elif key == 'Right':
                    self.right.append(value)
                elif key == 'Select':
                    self.select.append(value)


class WheelAnimation(QPropertyAnimation):
    def __init__(self, target, field, shadow_lbl):
        super().__init__(target, field)

        self.shadow_lbl = shadow_lbl


class VideoPlayer(QWidget):
    # noinspection PyArgumentList
    def __init__(self, width: int, height: int, parent=None):
        super(VideoPlayer, self).__init__(parent)
        video_item = QGraphicsVideoItem()
        video_item.setAspectRatioMode(Qt.IgnoreAspectRatio)
        video_item.setSize(QSizeF(width, height))
        scene = QGraphicsScene(self)
        scene.addItem(video_item)
        graphics_view = QGraphicsView(scene)
        graphics_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        graphics_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        layout = QVBoxLayout()
        layout.addWidget(graphics_view)
        self.setLayout(layout)
        self.mediaPlayer = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.mediaPlayer.setVideoOutput(video_item)
        self.mediaPlayer.setVolume(0)

    def play(self):
        self.mediaPlayer.play()

    def stop(self):
        self.mediaPlayer.stop()

    # noinspection PyArgumentList
    def load_loop(self, name):
        global config
        play_loop = QMediaPlaylist()
        play_loop.addMedia(QMediaContent(QUrl.fromLocalFile(config['preview_path'] + name)))
        play_loop.setPlaybackMode(QMediaPlaylist.Loop)
        self.mediaPlayer.setPlaylist(play_loop)

    # noinspection PyArgumentList
    def load(self, name):
        global config
        self.mediaPlayer.stop()
        if os.path.isfile(config['preview_path'] + name):
            local = QUrl.fromLocalFile(config['preview_path'] + name)
        else:
            local = QUrl.fromLocalFile(config['preview_path'] + 'default.mp4')
        media = QMediaContent(local)
        self.mediaPlayer.setMedia(media)


cur_timer = None


def try_preview():
    global cur_timer
    if cur_timer is not None:
        cur_timer.cancel()
    timer = Timer(0.6, start_preview)
    timer.start()
    cur_timer = timer


def start_preview():
    global v_player, cur_game, wheel_anims
    v_player.load(cur_game[0].name + '.mp4')
    v_player.play()


def start_game():
    global cur_game, config, v_player, bgm
    v_player.stop()
    bgm.stop()
    if cur_game[0].game_type == 'arcade':  # TODO extend to other types
        game = subprocess.Popen(config['mame_exec'] + ' %s' % cur_game[0].name + ' -rompath ' + config['rom_path']
                                + ' -skip_gameinfo')
    else:
        command = config['exe_path'] + cur_game[0].name + '.lnk'
        game = subprocess.Popen(command, shell=True)

    game.communicate()
    bgm.play()
    v_player.play()


def populate_games() -> [Game]:
    to_ignore = []
    with open('ignore.txt', 'r') as f:
        for line in f:
            to_ignore.append(line.rstrip('\n'))

    game_dict = {}
    with open('splash.txt') as s:
        for line in s:
            if line[0] == '*':
                continue
            line = line.split('|')
            game_dict[line[0]] = (line[1], line[2].rstrip('\n'))

    games = []
    dirs = (config['rom_path'], config['exe_path'])
    for direc in dirs:
        for file in os.listdir(direc):
            if file not in to_ignore:
                try:
                    info = game_dict[file]
                except KeyError:
                    print('Could not find info for ' + file + ', skipping')
                    continue
                if file.endswith(".zip"):
                    games.append(Game(file.rstrip('.zip'), info[0], info[1], 'arcade'))
                elif file.endswith('.lnk'):
                    games.append(Game(file.rstrip('.lnk'), info[0], info[1], 'exe'))
    games.sort()  # consider a better data structure?

    return games


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = VArcMain()
    ex.setObjectName('window')
    cursor = QCursor(Qt.BlankCursor)
    app.setOverrideCursor(cursor)
    app.changeOverrideCursor(cursor)
    app.setFont(QFont('Karmatic Arcade', 16, 400))
    sys.exit(app.exec_())
