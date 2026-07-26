<svelte:head>
  <title>Security Sync Dashboard</title>
  <meta
    name="description"
    content="Local security dashboard synced from Pico sensors and OpenCV host tracking."
  />
</svelte:head>

<script>
  import { onMount } from 'svelte';
  import anime from 'animejs/lib/anime.es.js';

  const initialState = {
    server: { connected: false, time: null },
    pico: {
      connected: false,
      armed: false,
      alarm: false,
      alarm_reason: 'idle',
      distance_cm: null,
      temperature_c: null,
      humidity: null,
      display_unit: 'C',
      last_seen: null
    },
    vision: {
      connected: false,
      person_name: 'No person',
      known: false,
      confidence: null,
      bbox: null,
      center: null,
      tracked: false,
      unknown_streak: 0,
      camera_index: 0
    },
    environment: {
      room_temperature_c: null,
      room_humidity: null,
      temperature_samples: 0
    },
    database: { count: 0, people: [], recognition: false },
    alarm: { active: false, reason: 'idle', source: 'none' },
    frame_version: 0,
    frame_ts: null,
    logs: []
  };

  let state = initialState;
  let error = '';
  let frameUrl = '/api/frame.jpg';
  let lastFrameVersion = -1;
  let lastAlarmActive = false;
  let refreshTimer = null;
  let frameTimer = null;
  let personName = '';
  let captureStatus = '';
  let captureInput;
  let capturePreview = '';

  // Reactive derived values
  $: picoData = state?.pico || {};
  $: envData = state?.environment || {};

  const clamp = (value, lower, upper) => Math.max(lower, Math.min(upper, value));

  function pushAlarmAnimation(active) {
    anime.remove('.warning-halo');
    anime.remove('.camera-shell');

    if (!active) {
      return;
    }

    anime({
      targets: '.warning-halo',
      opacity: [0.12, 0.5],
      scale: [1, 1.08],
      duration: 900,
      direction: 'alternate',
      easing: 'easeInOutSine',
      loop: true
    });

    anime({
      targets: '.camera-shell',
      translateY: [0, -2, 0],
      duration: 1200,
      easing: 'easeInOutSine',
      loop: true
    });
  }

  async function refreshState() {
    try {
      const response = await fetch('/api/state', { cache: 'no-store' });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      state = await response.json();
      console.log('Full API response:', JSON.stringify(state, null, 2));
      error = '';

      if (state.frame_version !== lastFrameVersion) {
        lastFrameVersion = state.frame_version;
        frameUrl = `/api/frame.jpg?t=${Date.now()}`;
      }

      if (state.alarm.active !== lastAlarmActive) {
        lastAlarmActive = state.alarm.active;
        pushAlarmAnimation(state.alarm.active);
      }
    } catch (err) {
      error = err?.message || 'Unable to reach the local bridge server.';
    }
  }

  function alarmActive() {
    return Boolean(state?.alarm?.active || state?.pico?.alarm);
  }

  function alarmLabel() {
    if (alarmActive()) return 'ON';
    return 'OFF';
  }

  function personLabel() {
    const name = state?.vision?.person_name || 'No person';
    if (name === 'No person') return 'No person';
    return state?.vision?.known ? name : `${name} outside DB`;
  }

  function distanceLabel() {
    const value = picoData?.distance_cm;
    console.log('Distance value:', value, 'picoData:', picoData);
    return value === null || value === undefined ? '-- cm' : `${value.toFixed(1)} cm`;
  }

  function roomTempText() {
    // Try pico first, then environment section
    const value = picoData?.temperature_c ?? envData?.room_temperature_c;
    console.log('Temp value:', value, 'pico:', picoData?.temperature_c, 'env:', envData?.room_temperature_c);
    return value === null || value === undefined ? '-- C' : `${value.toFixed(1)} C`;
  }

  function roomHumidityText() {
    // Try pico first, then environment section
    const value = picoData?.humidity ?? envData?.room_humidity;
    console.log('Humidity value:', value, 'pico:', picoData?.humidity, 'env:', envData?.room_humidity);
    return value === null || value === undefined ? '-- %' : `${value.toFixed(0)} %`;
  }

  function commandAlarm(enabled) {
    fetch('/api/alarm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled })
    }).catch(() => {});
  }

  function handleCaptureSelection(event) {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = () => {
      capturePreview = reader.result;
    };
    reader.readAsDataURL(file);
  }

  async function saveFaceSample() {
    if (!personName.trim() || !capturePreview) {
      captureStatus = 'Enter a name and take/select a photo first.';
      return;
    }

    captureStatus = 'Saving…';
    try {
      const response = await fetch('/api/people/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: personName.trim(), image: capturePreview })
      });
      const data = await response.json();
      if (!response.ok || !data.ok) {
        throw new Error(data.error || 'Could not save face sample.');
      }
      captureStatus = `Saved ${personName.trim()} to the people database.`;
      personName = '';
      capturePreview = '';
      if (captureInput) captureInput.value = '';
      await refreshState();
    } catch (err) {
      captureStatus = err?.message || 'Failed to save sample.';
    }
  }

  onMount(() => {
    refreshState();
    refreshTimer = setInterval(refreshState, 500);
    frameTimer = setInterval(() => {
      frameUrl = `/api/frame.jpg?t=${Date.now()}`;
    }, 900);

    return () => {
      clearInterval(refreshTimer);
      clearInterval(frameTimer);
      anime.remove('.warning-halo');
      anime.remove('.camera-shell');
    };
  });
</script>

<main class="shell">
  <section class="hero reveal">
    <div class="hero-copy">
      <div class="eyebrow">Local security sync</div>
      <h1>OpenCV tracking, Pico sensors, and alarm control in one dashboard.</h1>
      <p>
        The laptop camera tracks people locally with OpenCV, the Pico sends sensor data over USB,
        and the bridge keeps the website and buzzer in sync.
      </p>
      <div class="hero-actions">
        <button class="btn primary" on:click={() => commandAlarm(true)}>Arm alarm</button>
        <button class="btn ghost" on:click={() => commandAlarm(false)}>Silence alarm</button>
      </div>
    </div>

    <div class="status-stack">
      <div class="status-card reveal">
        <span>Alarm</span>
        <strong class:danger={alarmActive()}>{alarmLabel()}</strong>
        <small>{state?.alarm?.reason || 'idle'}</small>
      </div>
      <div class="status-card reveal">
        <span>Person</span>
        <strong>{personLabel()}</strong>
        <small>
          {state?.vision?.known ? 'Inside database' : 'Outside database'}
        </small>
      </div>
    </div>
  </section>

  <section class="dashboard-grid">
    <article class="camera-shell reveal">
      <div class="warning-halo"></div>
      <div class="panel-head">
        <div>
          <div class="panel-label">OpenCV camera</div>
          <h2>Tracked person</h2>
        </div>
        <div class="panel-chip" class:ok={state?.vision?.connected} class:wait={!state?.vision?.connected}>
          {state?.vision?.connected ? 'Live' : 'Offline'}
        </div>
      </div>

      <div class="camera-frame">
        {#if state?.vision?.connected}
          <img class="camera-feed" src={frameUrl} alt="Tracked camera frame" />
        {:else}
          <div class="frame-placeholder">
            <strong>No camera frame yet</strong>
            <span>Start `bridge.py` to connect the laptop camera.</span>
          </div>
        {/if}

        <div class="camera-overlay">
          <div class="overlay-badge" class:armed={state?.pico?.armed} class:neutral={!state?.pico?.armed}>
            {state?.pico?.armed ? 'ARMED' : 'DISARMED'}
          </div>
          <div class="overlay-badge" class:danger={alarmActive()} class:neutral={!alarmActive()}>
            {alarmLabel()}
          </div>
        </div>

        <div class="scan-strip">
          <span>Tracking: {state?.vision?.tracked ? 'active' : 'waiting'}</span>
          <span>DB match: {state?.vision?.known ? 'known' : 'unknown'}</span>
        </div>
      </div>

      <div class="metric-grid">
        <div class="metric-card">
          <span>Distance</span>
          <strong>{distanceLabel()}</strong>
        </div>
        <div class="metric-card">
          <span>Unknown streak</span>
          <strong>{state?.vision?.unknown_streak ?? 0}</strong>
        </div>
        <div class="metric-card">
          <span>Temp avg</span>
          <strong>{roomTempText()}</strong>
        </div>
        <div class="metric-card">
          <span>Humidity avg</span>
          <strong>{roomHumidityText()}</strong>
        </div>
      </div>
    </article>

    <aside class="control-stack">
      <section class="control-card reveal">
        <div class="panel-head">
          <div>
            <div class="panel-label">LCD1602</div>
            <h2>Distance and alarm</h2>
          </div>
          <div class="pill" class:danger={alarmActive()} class:ok={!alarmActive()}>
            {alarmActive() ? 'Buzzer on' : 'Buzzer off'}
          </div>
        </div>

        <div class="lcd">
          <div>{distanceLabel()}</div>
          <div>{alarmActive() ? 'ALARM: ON' : 'ALARM: OFF'}</div>
        </div>

        <div class="alarm-mini">
          <div>
            <span>Pico</span>
            <strong>{state?.pico?.connected ? 'Connected' : 'Offline'}</strong>
          </div>
          <div>
            <span>Display</span>
            <strong>{state?.pico?.display_unit || 'C'}</strong>
          </div>
        </div>
      </section>

      <section class="control-card reveal">
        <div class="panel-head">
          <div>
            <div class="panel-label">TM1637</div>
            <h2>Temperature display</h2>
          </div>
        </div>

        <div class="sensor-list">
          <div class="sensor-row">
            <span>Room temp</span>
            <strong>{roomTempText()}</strong>
          </div>
          <div class="sensor-row">
            <span>Room humidity</span>
            <strong>{roomHumidityText()}</strong>
          </div>
          <div class="sensor-row">
            <span>Samples averaged</span>
            <strong>{state?.environment?.temperature_samples ?? 0}</strong>
          </div>
          <div class="sensor-row">
            <span>Recognition DB</span>
            <strong>{state?.database?.count ?? 0} people</strong>
          </div>
        </div>
      </section>
    </aside>
  </section>

  <section class="feature-grid reveal">
    <article class="feature-card">
      <div class="feature-tag">Database</div>
      <h3>Known people</h3>
      <p>
        Unknown visitors trigger the buzzer after repeated detections. Known people stay silent.
      </p>
    </article>
    <article class="feature-card">
      <div class="feature-tag">OpenCV</div>
      <h3>Object tracking</h3>
      <p>
        The laptop camera tracks the person locally and keeps the website synced with the current
        target box and identity state.
      </p>
    </article>
    <article class="feature-card">
      <div class="feature-tag">Sensors</div>
      <h3>Averaged environment</h3>
      <p>
        DHT11 values are averaged before they reach the dashboard so the room temperature stays
        stable and readable.
      </p>
    </article>
    <article class="feature-card">
      <div class="feature-tag">Alarm</div>
      <h3>One-way buzzer</h3>
      <p>
        The buzzer is driven only when the tracked person is outside the saved database or the Pico
        raises a local sensor alarm.
      </p>
    </article>
  </section>

  <section class="bottom-grid">
    <article class="control-card reveal">
      <div class="panel-head">
        <div>
          <div class="panel-label">People DB</div>
          <h2>Saved people</h2>
        </div>
      </div>

      <div class="capture-box">
        <label class="capture-label" for="person-name">Person name</label>
        <input id="person-name" bind:value={personName} placeholder="e.g. Alice" />
        <input bind:this={captureInput} type="file" accept="image/*" on:change={handleCaptureSelection} />
        {#if capturePreview}
          <img class="capture-preview" src={capturePreview} alt="Selected face preview" />
        {/if}
        <button class="btn primary" on:click={saveFaceSample}>Save face sample</button>
        {#if captureStatus}
          <p class="capture-status">{captureStatus}</p>
        {/if}
      </div>

      <div class="db-grid">
        {#each (state?.database?.people || []) as person}
          <div class="db-card">
            <strong>{person.name}</strong>
            <span>{person.sample_count} samples</span>
          </div>
        {/each}
        {#if (state?.database?.people || []).length === 0}
          <div class="db-card empty">
            <strong>No people saved</strong>
            <span>Drop samples into `people_db/` to build the database.</span>
          </div>
        {/if}
      </div>
    </article>

    <article class="control-card reveal">
      <div class="panel-head">
        <div>
          <div class="panel-label">Event log</div>
          <h2>Synced state</h2>
        </div>
      </div>

      <div class="notes">
        <p>1. `bridge.py` serves the website locally and reads the Pico over USB.</p>
        <p>2. OpenCV tracking runs on the laptop camera, not on the Pico.</p>
        <p>3. The buzzer stays silent for known people and rings for outsiders.</p>
        <p>4. Temperature and humidity are averaged before the dashboard shows them.</p>
      </div>

      <ul class="log-list">
        {#each state?.logs || [] as event}
          <li class={event.tone}>
            <span>{event.time}</span>
            <strong>{event.message}</strong>
          </li>
        {/each}
      </ul>
    </article>
  </section>

  {#if error}
    <section class="error-box reveal">
      <strong>Bridge error</strong>
      <p>{error}</p>
    </section>
  {/if}
</main>
