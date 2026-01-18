"""
Metronome component for Guitar Shed.
Embedded HTML/JS metronome with BPM slider, tap tempo, and volume control.
"""

import streamlit as st


def render_metronome() -> None:
    """Render the metronome component."""
    st.subheader("Metronome")

    bpm_val = st.session_state.get('metronome_bpm', 120)

    st.components.v1.html(f"""
    <style>
        body {{ background: #1a1a1a; color: #ccc; font-family: sans-serif; margin: 0; padding: 5px; }}
        .met-container {{ border: 1px solid #333; padding: 10px; border-radius: 4px; background: #222; }}

        /* Layout classes */
        .top-row {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px; }}
        .control-group {{ margin-bottom: 8px; }}
        .label {{ font-size: 0.8rem; color: #888; margin-bottom: 2px; display: block; }}

        .bpm-display {{ font-size: 1.8rem; font-weight: bold; color: #fff; }}
        .time-sig-select {{ background: #333; color: #fff; border: 1px solid #444; padding: 2px 5px; }}

        /* Sliders */
        input[type=range] {{ width: 100%; accent-color: #555; background: transparent; cursor: pointer; }}

        /* Buttons */
        .btn-row {{ display: flex; gap: 5px; margin-top: 10px; }}
        button {{ flex: 1; background: #333; border: 1px solid #444; color: #ddd; padding: 8px; cursor: pointer; }}
        button:hover {{ background: #444; color: #fff; }}
        .active {{ background: #4a4a4a !important; color: #fff; }}
    </style>

    <div class="met-container">
        <div class="top-row">
            <span class="bpm-display" id="bpm">{bpm_val}</span>
            <select class="time-sig-select" id="ts">
                <option value="4">4/4</option>
                <option value="3">3/4</option>
                <option value="2">2/4</option>
                <option value="6">6/8</option>
            </select>
        </div>

        <!-- BPM SLIDER -->
        <div class="control-group">
            <input type="range" id="slider" min="40" max="220" value="{bpm_val}">
        </div>

        <!-- VOLUME SLIDER -->
        <div class="control-group" style="display: flex; align-items: center; gap: 10px;">
            <span class="label" style="width: 30px;">Vol</span>
            <input type="range" id="vol-slider" min="0" max="100" value="50">
        </div>

        <div class="btn-row">
            <button id="tap">TAP</button>
            <button id="start">START</button>
        </div>
    </div>

    <script>
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        let bpm = {bpm_val}, isPlaying = false, timer, nextNote = 0, beat = 0;

        // UI Elements
        const slider = document.getElementById('slider');
        const volSlider = document.getElementById('vol-slider');
        const disp = document.getElementById('bpm');
        const startBtn = document.getElementById('start');
        const tapBtn = document.getElementById('tap');
        const ts = document.getElementById('ts');

        let taps = [];
        let volume = 0.5; // Default volume

        function playSound(time, strong) {{
            // Create audio nodes
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();

            osc.connect(gain);
            gain.connect(ctx.destination);

            // Pitch: Strong beat = 600Hz, Weak beat = 400Hz
            osc.frequency.value = strong ? 600 : 400;

            // Volume Logic: Use the variable 'volume' instead of hardcoded 0.3
            // We ensure a tiny minimum (0.001) to prevent exponentialRamp errors if vol is 0
            const effectiveVol = Math.max(0.001, volume);

            gain.gain.setValueAtTime(effectiveVol, time);
            gain.gain.exponentialRampToValueAtTime(0.001, time + 0.1);

            osc.start(time);
            osc.stop(time + 0.1);
        }}

        function scheduler() {{
            while (nextNote < ctx.currentTime + 0.1) {{
                let measure = parseInt(ts.value);
                playSound(nextNote, beat % measure === 0);
                nextNote += 60.0 / bpm;
                beat++;
            }}
            timer = requestAnimationFrame(scheduler);
        }}

        // Event Listeners
        slider.oninput = function() {{ bpm = this.value; disp.innerText = bpm; }};

        volSlider.oninput = function() {{
            // Convert range 0-100 to 0.0-1.0
            volume = this.value / 100;
        }};

        startBtn.onclick = function() {{
            isPlaying = !isPlaying;
            if (isPlaying) {{
                if (ctx.state === 'suspended') ctx.resume();
                nextNote = ctx.currentTime;
                beat = 0;
                scheduler();
                this.innerText = "STOP";
                this.classList.add('active');
            }} else {{
                cancelAnimationFrame(timer);
                this.innerText = "START";
                this.classList.remove('active');
            }}
        }};

        tapBtn.onclick = function() {{
            let now = Date.now();
            if (taps.length && now - taps[taps.length-1] > 2000) taps = [];
            taps.push(now);
            if (taps.length > 4) taps.shift();
            if (taps.length > 1) {{
                let avg = taps.slice(1).map((t,i) => t - taps[i]).reduce((a,b)=>a+b)/ (taps.length-1);
                bpm = Math.round(60000/avg);
                if(bpm > 220) bpm = 220; if(bpm < 40) bpm = 40;
                slider.value = bpm; disp.innerText = bpm;
            }}
        }};
    </script>
    """, height=165)
