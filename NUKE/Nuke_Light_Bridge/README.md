# Nuke <> Maya Light Bridge 🌉

<p align="center">
  <strong>A powerful two-part toolkit designed to bridge the lighting workflow between Nuke and Maya.</strong>
</p>

<p align="center">
The Nuke Light Bridge allows compositors to perform a "technical relight" using AOV passes in Nuke and then seamlessly transfer those adjustments back to the original 3D lights in a Maya scene. This accelerates look development and ensures consistency between compositing and 3D.
</p>

<p align="center">
  <a href="https://vimeo.com/1134493543?fl=pl&fe=sh">
<img width="948" height="530" alt="Screenshot 2025-11-07 000927" src="https://github.com/user-attachments/assets/4573cc5f-9d9d-4d53-9824-2deb345f3f3c" /></a>
</p>

---

## 1. Overview

The project consists of two main components:

1.  **AOV Light Mixer (Nuke):** A tool that automatically builds a group node from a Read node's light AOVs. It provides a centralized UI to mix, grade, and adjust each light's contribution. The final adjustments can be exported as a `.json` file.
2.  **Light Bridge (Maya):** A simple utility that reads the exported `.json` file and applies the visibility, color, and exposure modifications to the corresponding lights in the Maya scene, using Arnold's AOV attributes as a link.

## 2. Nuke - AOV Light Mixer

<p align="center">
  <img width="296" height="253" alt="Nuke Light Mixer" src="https://github.com/user-attachments/assets/7092a4d8-a046-42c4-b415-96040844704d" />
</p>

This tool generates a `AOVLight_Mixer` node in Nuke to control your light passes.

### Features

*   **Automatic Setup:** Creates a node graph from a Read node containing light AOVs (channels must be prefixed with `RGBA_`).
*   **Centralized UI:** All controls are available directly on the node's properties panel.
*   **Per-Light Controls:**
    *   **Mute:** Toggle a light's contribution on or off.
    *   **Solo:** Isolate a single light, automatically muting all others. The tool intelligently restores the previous mute states when you unsolo.
    *   **Color:** Adjust the tint of a light.
    *   **Exposure:** Modify the light's intensity in `stops`.
*   **Global Controls:** `Mute All` and `Unmute All` buttons for quick adjustments.
*   **Data Export:** In one click, the button `export` will saves all light adjustments to a `.json` file.

### Installation & Setup (Nuke)

1.  **Place the Tool Folder:**
    *   Copy the entire `Nuke_Light_Bridge` folder into your Nuke plugins directory. A common location is your user's `.nuke` folder (e.g., `C:/Users/YourUser/.nuke/`).
    *   If it's not done yet create a `init.py` file in directory(`C:/Users/YourUser/.nuke/`) and write in it : `nuke.pluginAddPath(r'YOUR_PATH/Nuke_Light_Bridge')`.
    

2.  **Set the Export Path (Crucial Step):**
    *   Open the file: `Nuke_Light_Bridge/init.py`.
    *   Find the line: `JSON_PATH = r"Put Your Path Here, where your json files will be exported !"`
    *   **You must change this path** to a valid directory on your system where you want the `.json` files to be saved. For example:
        ```python
        JSON_PATH = r"D:\projects\my_shot\lighting\nuke_exports\"
        ```

3.  **Launch Nuke:**
    *   Nuke will automatically run the `menu.py` script, which adds a new menu named **"Light Bridge"** to the main toolbar.

---

## 3. Maya - Light Bridge

<p align="center">
  <img width="605" height="363" alt="Maya Light Bridge" src="https://github.com/user-attachments/assets/5b6e48ed-e7c4-4e2e-bfe1-96f624f7f428" />
</p>

This simple utility applies the lighting data from the exported `.json` file to your Maya scene.

### Prerequisites

*   **Arnold Renderer:** The logic relies on Arnold's `aiAov` attribute to link Nuke passes to Maya lights.
*   **Qt.py:** This UI framework is required. If you don't have it, download `Qt.py` and place it in your Maya scripts folder: `C:\Users\YOUR_USERNAME\Documents\maya\MAYA_VERSION\scripts`.

### How it Works

The bridge matches lights based on the **AOV Group** name.

*   In Nuke, the tool looks for AOVs like `RGBA_key`. The light name is `key`.
*   In Maya, the corresponding light's **Transform node** must have an Arnold attribute `aiAov` set to that same name (`key`).

### Installation & Setup (Maya)

1.  **Set the Tool Path:**
    *   Open the file `Nuke_Light_Bridge/bridge_launcher_.py` in a text editor.
    *   Find the line: `directory = r"YOUR_PATH\Nuke_Light_Bridge"`
    *   **You must change this path** to the location where you have stored the `Nuke_Light_Bridge` folder. For example:
        ```python
        directory = r"D:\tools\Nuke_Light_Bridge"
        ```

2.  **Create a Shelf Button:**
    *   Open Maya.
    *   Open the Script Editor (`Windows > General Editors > Script Editor`).
    *   Go to the `Python` tab.
    *   Copy the entire content of the modified `bridge_launcher_.py` script and paste it into the Script Editor.
    *   Select all the text you just pasted (`Ctrl+A`).
    *   With the text selected, middle-mouse-drag it onto one of your shelves. A Python icon will appear.
    *   You can right-click the new shelf button to edit its icon and name.
---

## 4. Workflow

### Workflow (Maya)

1.  **Prepare Your Scene:**
    *   Ensure all lights you want to control have the **Arnold > AOV Group** attribute (`aiAov`) set on their **shape node**.

2.  **Render your EXR:**
    *   Render your scene with Arnold, ensuring that all desired light AOVs are enabled.
    *  Don't forget to have `Merge AOVs` checked in your render settings.

### Workflow (Nuke)

3.  **Select Read Node:** In your Nuke script, select the Read node that contains your rendered EXR with all the light AOVs (e.g., `RGBA_key`, `RGBA_fill`, `RGBA_rim`).

4.  **Create The Light Mixer:** Go to the **Light Bridge** menu and click **Create LightMixer Node**.

5.  **Adjust Lights:** A new node named `AOVLight_Mixer` will be created and connected to your Read node. Select it and go to its Properties panel. Use the `AOVLight_Mixer` tab to make your lighting adjustments.

6.  **Export Data:** Once you are happy with the look, click the **Export** button at the bottom of the properties panel.

7.  **Check Output:** A `.json` file will be created in the directory you specified in `init.py`. The file will be named using the shot name and a timestamp (e.g., `shot01_2025-11-05__10h30m15s.json`). A confirmation message will appear in Nuke.

### Back to Workflow (Maya)

8.  **Launch the Tool:**
    *   Click your newly created shelf button. A small "Light Bridge" window will appear and stay on top of Maya.

9.  **Import Data:**
    *   Click the **Open File** button.
    *   Navigate to and select the `.json` file you exported from Nuke.

10.  **Verify Changes:**
    *   The script will immediately apply the data. It will update the following attributes for each matching light:
        *   **Visibility:** The light will be turned on or off based on the `Mute` state.
        *   **Color:** The light's color will be adjusted by the color value from Nuke.
        *   **Exposure:** The exposure value from Nuke will be added to the light's current exposure.
        
        * The Maya Script Editor will print in the console a confirmation for each light that was successfully updated.


