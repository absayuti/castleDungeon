"""
    Castle Dungeon Cardputer Microhydra MicroPython
    
    V 0.20
"""
import framebuf, random, time, machine
from lib import display, userinput
from lib.hydra import config
from machine import I2S, Pin
from font import vga1_8x16

#===============================================================================
#								Global definitions
#===============================================================================
#
# Dimensions of sprites
SPRITE_W = 45
SPRITE_H = 45
BYTES_PER_PIXEL = 2 # RGB565 uses 2 bytes per pixel
#
# Screen coordinates for info area (left)
BX0 = 0; BX1 = BX0+34; BX2 = BX1+34
BY0 = 16; BY1 = BY0+34; BY2 = BY1+34; BY3 = BY2+34
SW = SPRITE_W; SH = SPRITE_H
#
# Screen coordinates for play area (right)
X0 = 104; X1 = X0+45; X2 = X1+45
Y0 = 0;   Y1 = Y0+45; Y2 = Y1+45
#
# Colours
WHITE = 0xFFFF; BLACK = 0x0000
RED = 0xF800; GREEN = 0x07E0; BLUE = 0x001F;
YELLOW = 0xFFE0; CYAN = 0x07FF; MAGENTA = 0xF81F; PURPLE = 0xE0FF;
GRAY = 	0x8410; LIGHTGRAY = 0xDEFB; DARKGRAY = 0x4208
#
#
# Game parameters and variables
ROW = 20; COL = 20;
maze = ["X" * COL] * ROW
row = 1; col = 1
MAXTIME = 300
secondsleft = MAXTIME
playgame = 1
gameover = 0;
ukey, usword, uspell, ubombs = 0, 0, 0, 0 
facing = 1;
#// Variables for timer
#unsigned long prevMillis = 0;
#const long INTERVAL = 1000;   // Interval in milliseconds (1 second)
#const long SECONDS = 300;     // Game time = 5 minutes
#int secondsLeft;   

#
# The empty maze template
emptyMaze = [
  "####################",
  "#..#..#     #      #",
  "#..#..# ### # ##-# #",
  "#-###-# #   # #..# #",
  "# #   # # ###-#..# #",
  "# # # # #  #..#### #",
  "#   # #-## #..#    #",
  "##### #..# #### ####",
  "#     #..# #..# #..#",
  "# ###-#### #..# #..#",
  "# #......# ##-# ##-#",
  "# ########         #",
  "#          ####### #",
  "# ## ## ####       #",
  "####  # #..# #####-#",
  "#..####-#..# # #...#",
  "#..#....##-# # #####",
  "#-######## #    ...#",
  "#            #######",
  "####################"
]

# Calculate the buffer size and load the binary data from the file
buffer_size = SPRITE_W * SPRITE_H * BYTES_PER_PIXEL
sprite_data = bytearray(buffer_size)
sprite2_data = bytearray(buffer_size)
#data_manright = bytearray(buffer_size)
#data_floor    = bytearray(buffer_size)
#data_wall     = bytearray(buffer_size)
#data_door     = bytearray(buffer_size)
#data_beast    = bytearray(buffer_size)

# Initialize your MicroHydra display (using its internal framebuffer/canvas)
# Note: Depending on your MicroHydra version, you may use display.canvas or display.get_buffer()
DISPLAY = display.Display()
CONFIG = config.Config()
INPUT = userinput.UserInput()

# Initialize I2S on the Cardputer's NS4168 amplifier pins
audio_out = I2S(
    0,
    sck=Pin(41),
    ws=Pin(43),
    sd=Pin(42),
    mode=I2S.TX,
    bits=16,
    format=I2S.MONO,
    rate=16000,
    ibuf=2000
)


#===============================================================================
#								Function definitions
#===============================================================================
    
#-------------------------------------------------------------------------------
# Downscale and blit function
def scale_blit(raw_bytes, xcoord, ycoord, orig_w, orig_h, scale_factor=0.5):
    new_w = max(1, int(orig_w * scale_factor))
    new_h = max(1, int(orig_h * scale_factor))
    scaled = bytearray(new_w * new_h * 2)
    
    # Pre-calculate horizontal X byte offsets for speed
    x_offsets = [((x * orig_w) // new_w) * 2 for x in range(new_w)]
    
    dst_idx = 0
    for y in range(new_h):
        src_y_offset = ((y * orig_h) // new_h) * orig_w * 2
        for x_off in x_offsets:
            src_idx = src_y_offset + x_off
            scaled[dst_idx] = raw_bytes[src_idx]
            scaled[dst_idx + 1] = raw_bytes[src_idx + 1]
            dst_idx += 2
            
    scaled_fb = framebuf.FrameBuffer(scaled, new_w, new_h, framebuf.RGB565), new_w, new_h
    DISPLAY.blit_buffer(scaled, xcoord, ycoord, new_w, new_h, key=0xFFFF)

#-------------------------------------------------------------------------------
# Read sprite image from file and buffer it
def get_sprite( filename ):
    try:
        with open( filename, "rb") as f:
            f.readinto(sprite_data)
    except OSError:
        print("Error: Could not find or read "+filename)
    
    sprite_fb = framebuf.FrameBuffer(sprite_data, SPRITE_W, SPRITE_H, framebuf.RGB565)

#-------------------------------------------------------------------------------
# Put item at random place in maze 
def place_item( ch, n ):
    for i in range(n):
        while True:
            r = random.randint(1, ROW-1)
            c = random.randint(1, COL-1)
            #DISPLAY.text(str(r),0,0,WHITE,font=vga1_8x16)
            #DISPLAY.text(maze[r][c],20,0,WHITE,font=vga1_8x16)
            if maze[r][c]==' ':
                break
        maze[r] = maze[r][:c] + ch + maze[r][c+1:]

#-------------------------------------------------------------------------------
# Put item at random place in a room (cell marked by a '.')       
def place_item_room( ch, n ):
    for i in range(n):
        while True:
            r = random.randint(1, ROW-1)
            c = random.randint(1, COL-1)
            if maze[r][c]=='.':
                break
        maze[r] = maze[r][:c] + ch + maze[r][c+1:]

#-------------------------------------------------------------------------------
# Setup maze for game
def setup_maze():
    for r in range(ROW):
        maze[r] = emptyMaze[r]
    # Place items at random places in maze
    place_item_room('X', 3)  # Explosives = bombs
    place_item_room('B',12)  # Beasts
    place_item('P', 3)       # Pits
    place_item('K', 1)       # Key
    place_item('S', 1)       # Sword

#-------------------------------------------------------------------------------
# Reset game variables
def reset_gamevars():
    global ukey, usword, ubombs, uspell, facing
    global secondsleft, MAXTIME, gameover
    global row, col
    ukey = 0
    usword = 0
    ubombs = 0
    uspell = 0
    facing = 0
    secondsleft = MAXTIME
    gameover = 0
    # Start player at random location
    while True:
        row = random.randint(1, ROW-1)
        col = random.randint(1, COL-1)
        if maze[row][col]==' ':
            break
    
#-------------------------------------------------------------------------------
# Draw play area
def draw_playfield():
    for r in range(3):
        for c in range(3):
            #print(row+r-1, col+c-1)
            ch = maze[row+r-1][col+c-1]
            if ch=='#':
                get_sprite("raw/wall.raw")
            elif ch=='-':
                get_sprite("raw/door.raw")
            elif ch=='X':
                get_sprite("raw/bomb.raw")
            elif ch=='B':
                get_sprite("raw/beast.raw")
            elif ch=='P':
                get_sprite("raw/pit.raw")
            elif ch=='K':
                get_sprite("raw/key.raw")
            elif ch=='S':
                get_sprite("raw/sword.raw")
            else:
                get_sprite("raw/floor.raw")
            DISPLAY.blit_buffer(sprite_data, X0+c*SW, Y0+r*SH, SW, SH)
            # Show player in middle/centre
            if facing:
                get_sprite("raw/man-right.raw")
            else:
                get_sprite("raw/man-left.raw")
            DISPLAY.blit_buffer(sprite_data, X0+SW, Y0+SH, SW, SH, key=WHITE)
    
#-------------------------------------------------------------------------------
# Setup info AREA
def setup_info():
    for i in range(3):
        DISPLAY.fill_rect(BX0+i*34, BY0, 30, 30, GRAY)
        DISPLAY.fill_rect(BX0+i*34, BY1, 30, 30, GRAY)

#-------------------------------------------------------------------------------
# Update info area
def update_info():
    global ukey, usword, ubombs, spell
    setup_info()
    if ukey:
        get_sprite("raw/key.raw")
        scale_blit(sprite_data, BX0, BY0, SW, SH, scale_factor=0.6)
    if usword:
        get_sprite("raw/sword.raw")
        scale_blit(sprite_data, BX1, BY0, SW, SH, scale_factor=0.6)
    if uspell:
        get_sprite("raw/spell.raw")
        scale_blit(sprite_data, BX2, BY0, SW, SH, scale_factor=0.6)
    get_sprite("raw/bomb.raw")
    if ubombs: 
        scale_blit(sprite_data, BX0, BY1, SW, SH, scale_factor=0.6)
    if ubombs>1:
        scale_blit(sprite_data, BX1, BY1, SW, SH, scale_factor=0.6)
    if ubombs>2:
        scale_blit(sprite_data, BX2, BY1, SW, SH, scale_factor=0.6)

#-------------------------------------------------------------------------------
# Draw cursor showing player's motion
def draw_cursor( rr, cc ):
    DISPLAY.fill_rect(BX0, BY2, 103, 52, BLACK)
    if rr==-1:
        get_sprite("raw/arrow-up.raw")
        scale_blit(sprite_data, BX1, BY2, SW, SH, scale_factor=0.6)
    elif rr==1:
        get_sprite("raw/arrow-down.raw")
        scale_blit(sprite_data, BX1, BY2+25, SW, SH, scale_factor=0.6)
    if cc==-1:
        get_sprite("raw/arrow-left.raw")
        scale_blit(sprite_data, BX1-25, BY2+12, SW, SH, scale_factor=0.6)
    if cc==1:
        get_sprite("raw/arrow-right.raw")
        scale_blit(sprite_data, BX1+25, BY2+12, SW, SH, scale_factor=0.6)
        
        
#-------------------------------------------------------------------------------
# Remove item
def remove_item():
    maze[row] = maze[row][:col] + ' ' + maze[row][col+1:]
    beep(200)
   
#-------------------------------------------------------------------------------
# Bump into door
def bump_door():
    get_sprite("raw/floor.raw")
    DISPLAY.blit_buffer(sprite_data, X1, Y1, SW, SH)
    if facing:
        get_sprite("raw/man-right.raw")
    else:
        get_sprite("raw/man-left.raw")
    DISPLAY.blit_buffer(sprite_data, X1, Y1+rr*22, SW, SH, key=WHITE)
    DISPLAY.show()
    beep(100)
      
#-------------------------------------------------------------------------------
# Play the tone for msec mseconds
def beep( msec ):
    # Create one cycle of a 1000 Hz square wave (16 samples at 16 kHz)
    # 16-bit signed little-endian: +4000 (0x0FA0) and -4000 (0xF060)
    high = b'\xa0\x0f' * 8
    low = b'\x60\xf0' * 8
    wave_cycle = high + low
    for _ in range(msec):
        audio_out.write(wave_cycle)

#-------------------------------------------------------------------------------
# Play the tone for msec mseconds
def buzz( msec ):
    for _ in range(msec/50):
        beep(5)
        time.sleep_ms(50)

#===============================================================================
#								   Main 
#===============================================================================

while True:

    DISPLAY.fill(BLACK)
    setup_info()
    setup_maze()
    reset_gamevars()
    draw_playfield()
    update_info()
    beep(100)   
    timeprev = time.ticks_ms()
   
    while gameover==0:
        # Read keyboard
        rr = 0; cc = 0
        text = ''    
        keys = INPUT.get_new_keys()
        if keys:
            text = str(keys)
        if 'l' in text:
            uspell = 1
            print(uspell)
            beep(50)
            update_info()
        elif ';' in text:
            rr = -1
        elif '.' in text:
            rr = 1
        elif ',' in text:
            cc = -1
            facing = 0
        elif '/' in text:
            cc = 1
            facing = 1
        # Move player
        if rr!=0 or cc!=0:
            if maze[row+rr][col+cc]!='#':
                row = row+rr
                col = col+cc
                ch = maze[row][col]
                if ch=='-':
                    if ukey==1:
                        remove_item()  # Open door                        
                    else:
                        bump_door()
                        row = row-rr
                        col = col-cc
                elif ch=='X':
                    ubombs = ubombs+1
                    if ubombs==3:
                        gameover = 1
                    remove_item()
                    update_info()
                elif ch=='K':
                    ukey = 1
                    remove_item()
                    update_info()
                elif ch=='S':
                    usword = 1
                    remove_item()
                    update_info()
                elif ch=='B':
                    buzz(500)
                    if usword:
                        remove_item()
                    else:
                        gameover = 2
                elif ch=='P':
                    if uspell:
                        beep(50)
                    else:
                        buzz(500)
                        gameover = 3
            if uspell==2:
                uspell=0
                print(uspell)
                update_info()
            if uspell==1:
                uspell=2
                print(uspell)
            draw_playfield()
            draw_cursor(rr,cc)
        # Display ??? for debugging
        #DISPLAY.fill_rect(0,0,30,16, GRAY)
        #DISPLAY.text(str(gameover),0,0,WHITE,font=vga1_8x16)
        # Display timer
        DISPLAY.fill_rect(0,0,104,16, BLACK)
        DISPLAY.text(f"Time: {secondsleft:02d}",0,0,WHITE,font=vga1_8x16)
        # Push the updated frame to the physical hardware display
        DISPLAY.show()
        # Pause a while
        time.sleep_ms(1)
        
        timenow = time.ticks_ms()
        if timenow - timeprev > 1000:
            timeprev = timenow
            secondsleft = secondsleft - 1
            if secondsleft <= 0:
                gameover = 4
            #print(secondsleft)
        
    # Game over
    beep(500)
    DISPLAY.fill(BLACK)
    if gameover==1:
        text = "YOU SAVED THE CASTLE"
    elif gameover==2:
        text = "YOU LOST TO A BEAST"
    elif gameover==3:
        text = "YOU FELL INTO A PIT"
    else:
        DISPLAY.text("TIME'S UP!",60,60,WHITE,font=vga1_8x16)
        DISPLAY.show()
        time.sleep_ms(1500)
        DISPLAY.fill(BLACK)
        text = "  CASTLE DESTROYED!"
    DISPLAY.text(text,40,60,WHITE,font=vga1_8x16)
    DISPLAY.show()
    time.sleep_ms(5000)
    gameover = 0
    
        
#===============================================================================
#								   End 
#===============================================================================


