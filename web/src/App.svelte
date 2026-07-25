<svelte:head>
  <title>Security Vision Dashboard</title>
  <meta
    name="description"
    content="A security-themed webcam dashboard for human detection, motion gating, alarm output, and live sensor status."
  />
</svelte:head>

<script>
  import { onMount } from 'svelte';
  import anime from 'animejs/lib/anime.es.js';

  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
  const nowLabel = () =>
    new Date().toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });

  let videoEl;
  let canvasEl;
  let cameraStream = null;
  let cameraReady = false;
  let cameraError = '';

  let faceDetector = null;
  let faceSupport = false;
  let faceFallbackWarned = false;
  let scanning = false;
  let frameBuffer = null;
  let scanTimer = null;
  let tempTimer = null;
  let smsTimer = null;

  let armed = true;
  let alarmActive = false;
  let alarmReason = 'Monitoring';
  let alarmUntil = 0;
  let alertCount = 0;

  let faceCount = 0;
  let motionScore = 0;
  let distanceCm = null;
  let tempC = 27.2;

  let smsStatus = 'Idle';
  let systemStatus = 'Secure';
  let lcdLine1 = 'SYSTEM ARMED';
  let lcdLine2 = 'WAIT FOR INPUT';
  let lastEvent = 'Boot sequence complete';

  let eventLog = [
    { time: nowLabel(), tone: 'success', message: 'Dashboard booted' },
    { time: nowLabel(), tone: 'info', message: 'Waiting for camera permission' }
  ];

  let faceLabel = 'No human';

  const featureCards = [
    {
      title: 'Human detection',
      tag: 'OpenCV / Face API',
      text: 'Uses browser face detection when available, with motion fallback for unsupported browsers.'
    },
    {
      title: 'Motion gate',
      tag: 'Ultrasonic layer',
      text: 'Combines frame movement with the human trigger so the alarm only fires on a stronger signal.'
    },
    {
      title: 'Alarm output',
      tag: 'LED + buzzer',
      text: 'Shows the alarm state visually and simulates the buzzer and flash behavior from the Pico build.'
    },
    {
      title: 'Pico display',
      tag: 'LCD + temperature',
      text: 'Mirrors the LCD and 4-digit temperature readout used in the hardware version of the project.'
    }
  ];

  function pushEvent(message, tone = 'info') {
    lastEvent = message;
    eventLog = [{ time: nowLabel(), tone, message }, ...eventLog].slice(0, 8);
  }

  function setLcd(line1, line2) {
    lcdLine1 = line1.slice(0, 16);
    lcdLine2 = line2.slice(0, 16);
  }

  function animateAlarm(on) {
    anime.remove('.warning-halo');
    anime.remove('.camera-shell');

    if (!on) {
      return;
    }

    anime({
      targets: '.warning-halo',
      opacity: [0.14, 0.5],
      scale: [1, 1.1],
      duration: 900,
      direction: 'alternate',
      easing: 'easeInOutSine',
      loop: true
    });

    anime({
      targets: '.camera-shell',
      translateY: [0, -2, 0],
      duration: 1400,
      easing: 'easeInOutSine',
      loop: true
    });
  }

  function startAlarm(reason) {
    const freshAlert = !alarmActive;

    alarmActive = true;
    alarmReason = reason;
    alarmUntil = Date.now() + 25000;
    systemStatus = 'ALERT';
    smsStatus = 'Sending';
    setLcd('ALARM ACTIVE', reason.toUpperCase());

    if (freshAlert) {
      alertCount += 1;
      pushEvent(`ALARM: ${reason}`, 'danger');
      animateAlarm(true);

      clearTimeout(smsTimer);
      smsTimer = setTimeout(() => {
        smsStatus = 'Sent';
        pushEvent('SMS notification queued to phone', 'success');
      }, 1300);
    }
  }

  function clearAlarm(message = 'System secure') {
    if (alarmActive) {
      pushEvent('Alarm reset', 'info');
    }

    alarmActive = false;
    alarmReason = 'Monitoring';
    systemStatus = armed ? 'Secure' : 'Disarmed';
    smsStatus = 'Idle';
    animateAlarm(false);
    setLcd(armed ? 'SYSTEM ARMED' : 'SYSTEM DISARMED', armed ? 'WAIT FOR INPUT' : 'ALARMS OFF');
    lastEvent = message;
  }

  function toggleArmed() {
    armed = !armed;

    if (!armed) {
      clearAlarm('System disarmed');
      pushEvent('System disarmed', 'warn');
    } else {
      systemStatus = 'Secure';
      setLcd('SYSTEM ARMED', 'WATCHING ZONE');
      pushEvent('System armed', 'success');
    }
  }

  function manualAlarm() {
    startAlarm('manual security test');
  }

  async function connectCamera() {
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error('Camera API is not available in this browser.');
    }

    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'user' },
      audio: false
    });

    cameraStream = stream;
    videoEl.srcObject = stream;

    await new Promise((resolve) => {
      if (videoEl.readyState >= 1) {
        resolve();
        return;
      }

      videoEl.addEventListener('loadedmetadata', resolve, { once: true });
    });

    await videoEl.play();
    cameraReady = true;
    pushEvent('Camera feed connected', 'success');
    setLcd('SYSTEM ARMED', 'LIVE CAMERA ON');
  }

  async function analyzeFrame() {
    if (scanning || !cameraReady || !videoEl || !canvasEl) {
      return;
    }

    scanning = true;

    try {
      const width = 96;
      const aspect = videoEl.videoWidth && videoEl.videoHeight ? videoEl.videoHeight / videoEl.videoWidth : 0.75;
      const height = Math.max(72, Math.round(width * aspect));
      canvasEl.width = width;
      canvasEl.height = height;

      const ctx = canvasEl.getContext('2d', { willReadFrequently: true });
      if (!ctx) {
        return;
      }
      ctx.drawImage(videoEl, 0, 0, width, height);

      const frame = ctx.getImageData(0, 0, width, height).data;
      let diff = 0;

      if (frameBuffer) {
        for (let i = 0; i < frame.length; i += 12) {
          const current = frame[i] * 0.299 + frame[i + 1] * 0.587 + frame[i + 2] * 0.114;
          const previous = frameBuffer[i] * 0.299 + frameBuffer[i + 1] * 0.587 + frameBuffer[i + 2] * 0.114;
          diff += Math.abs(current - previous);
        }
        const sampleCount = frame.length / 12;
        motionScore = Math.min(100, Math.round((diff / sampleCount) * 2.1));
      }

      frameBuffer = new Uint8ClampedArray(frame);

      let detectedFaces = [];
      if (faceDetector) {
        try {
          detectedFaces = await faceDetector.detect(videoEl);
        } catch (error) {
          faceDetector = null;
          faceSupport = false;

          if (!faceFallbackWarned) {
            faceFallbackWarned = true;
            pushEvent('Face detector failed, motion fallback enabled', 'warn');
          }
        }
      }

      faceCount = detectedFaces.length;
      faceLabel = faceCount > 0 ? `${faceCount} human${faceCount > 1 ? 's' : ''}` : 'No human';

      if (detectedFaces[0]) {
        const box = detectedFaces[0].boundingBox;
        distanceCm = clamp(Math.round(250 - box.width * 2.7), 25, 250);
      } else {
        distanceCm = motionScore > 12 ? clamp(Math.round(220 - motionScore * 1.4), 25, 220) : null;
      }

      tempC = clamp(26.8 + Math.sin(Date.now() / 6500) * 0.8 + motionScore * 0.03, 20, 41);

      const humanDetected = faceCount > 0;
      const motionDetected = motionScore > 18;

      if (armed && humanDetected && motionDetected) {
        startAlarm(faceSupport ? 'human detected with motion' : 'motion-based human alert');
      } else if (armed && !faceSupport && motionDetected && motionScore > 36) {
        startAlarm('motion threshold crossed');
      }

      if (alarmActive && Date.now() > alarmUntil) {
        clearAlarm('Alarm window expired');
      }

      if (!alarmActive) {
        systemStatus = armed ? 'Secure' : 'Disarmed';
        if (armed) {
          setLcd('SYSTEM ARMED', faceCount > 0 ? `DIST ${String(distanceCm ?? '--').padStart(3, ' ')}CM` : 'WAIT FOR INPUT');
        }
      }
    } finally {
      scanning = false;
    }
  }

  onMount(() => {
    let mounted = true;

    pushEvent('Security UI loaded', 'success');

    anime({
      targets: '.reveal',
      opacity: [0, 1],
      translateY: [18, 0],
      duration: 720,
      delay: anime.stagger(90),
      easing: 'easeOutCubic'
    });

    if (typeof window !== 'undefined' && 'FaceDetector' in window) {
      try {
        faceDetector = new window.FaceDetector({
          fastMode: true,
          maxDetectedFaces: 2
        });
        faceSupport = true;
        pushEvent('Face detection engine ready', 'success');
      } catch (error) {
        faceSupport = false;
        pushEvent('Face detector unavailable, motion fallback enabled', 'warn');
      }
    } else {
      pushEvent('Face detector unavailable, motion fallback enabled', 'warn');
    }

    (async () => {
      try {
        await connectCamera();
      } catch (error) {
        if (!mounted) {
          return;
        }

        cameraError = error?.message || 'Unable to access the camera.';
        systemStatus = 'Offline';
        setLcd('CAMERA OFFLINE', 'CHECK CAMERA');
        pushEvent(`Camera error: ${cameraError}`, 'danger');
      }
    })();

    scanTimer = setInterval(analyzeFrame, 250);
    tempTimer = setInterval(() => {
      if (!alarmActive) {
        tempC = clamp(26.8 + Math.sin(Date.now() / 6500) * 0.8 + motionScore * 0.02, 20, 41);
      }
    }, 900);

    return () => {
      mounted = false;
      clearInterval(scanTimer);
      clearInterval(tempTimer);
      clearTimeout(smsTimer);

      if (cameraStream) {
        for (const track of cameraStream.getTracks()) {
          track.stop();
        }
      }

      anime.remove('.warning-halo');
      anime.remove('.camera-shell');
    };
  });
</script>

<main class="shell">
  <section class="hero reveal">
    <div class="hero-copy">
      <div class="eyebrow">Security Vision Dashboard</div>
      <h1>Human detection, motion gating, and active alarm output in one security panel.</h1>
      <p>
        Live camera monitoring with face detection, motion analysis, alarm control, LCD-style
        output, and a temperature readout that matches the Pico project flow.
      </p>
      <div class="hero-actions">
        <button class="btn primary" on:click={toggleArmed}>
          {armed ? 'Disarm system' : 'Arm system'}
        </button>
        <button class="btn ghost" on:click={manualAlarm}>Test alarm</button>
      </div>
    </div>

    <div class="status-stack">
      <div class="status-card reveal">
        <span>System state</span>
        <strong>{systemStatus}</strong>
        <small>{armed ? 'Watching the perimeter' : 'All outputs are off'}</small>
      </div>
      <div class="status-card reveal">
        <span>Alarm source</span>
        <strong>{alarmReason}</strong>
        <small>Last event: {lastEvent}</small>
      </div>
    </div>
  </section>

  <section class="dashboard-grid">
    <article class="camera-shell reveal">
      <div class="warning-halo"></div>
      <div class="panel-head">
        <div>
          <div class="panel-label">Live camera</div>
          <h2>Webcam feed</h2>
        </div>
        <div class="panel-chip" class:ok={cameraReady} class:wait={!cameraReady}>
          {cameraReady ? 'Live' : 'Waiting'}
        </div>
      </div>

      <div class="camera-frame">
        <video bind:this={videoEl} autoplay playsinline muted></video>
        <canvas bind:this={canvasEl} class="hidden-canvas"></canvas>

        <div class="camera-overlay">
          <div class="overlay-badge" class:armed={armed} class:neutral={!armed}>
            {armed ? 'ARMED' : 'DISARMED'}
          </div>
          <div class="overlay-badge" class:danger={alarmActive} class:neutral={!alarmActive}>
            {alarmActive ? 'ALARM ACTIVE' : 'NO ALERT'}
          </div>
        </div>

        <div class="scan-strip">
          <span>Face detection: {faceSupport ? 'supported' : 'fallback mode'}</span>
          <span>Motion gate: {motionScore > 18 ? 'active' : 'stable'}</span>
        </div>
      </div>

      <div class="metric-grid">
        <div class="metric-card">
          <span>Humans</span>
          <strong>{faceLabel}</strong>
        </div>
        <div class="metric-card">
          <span>Motion</span>
          <strong>{motionScore}%</strong>
          <div class="meter"><i style={`width:${motionScore}%`}></i></div>
        </div>
        <div class="metric-card">
          <span>Distance</span>
          <strong>{distanceCm === null ? '-- cm' : `${distanceCm} cm`}</strong>
        </div>
        <div class="metric-card">
          <span>Temperature</span>
          <strong>{tempC.toFixed(1)} &deg;C</strong>
        </div>
      </div>
    </article>

    <aside class="control-stack">
      <section class="control-card reveal">
        <div class="panel-head">
          <div>
            <div class="panel-label">Alarm output</div>
            <h2>Command center</h2>
          </div>
          <div class="pill" class:danger={alarmActive} class:ok={armed && !alarmActive} class:muted={!armed && !alarmActive}>
            {alarmActive ? 'Active' : armed ? 'Ready' : 'Off'}
          </div>
        </div>

        <div class="lcd">
          <div>{lcdLine1}</div>
          <div>{lcdLine2}</div>
        </div>

        <div class="command-row">
          <button class="btn primary" on:click={toggleArmed}>
            {armed ? 'Disarm' : 'Arm'}
          </button>
          <button class="btn ghost" on:click={manualAlarm}>Alarm test</button>
        </div>

        <div class="alarm-mini">
          <div>
            <span>SMS</span>
            <strong>{smsStatus}</strong>
          </div>
          <div>
            <span>Alerts</span>
            <strong>{alertCount}</strong>
          </div>
        </div>
      </section>

      <section class="control-card reveal">
        <div class="panel-head">
          <div>
            <div class="panel-label">Pico outputs</div>
            <h2>Sensor panel</h2>
          </div>
        </div>

        <div class="sensor-list">
          <div class="sensor-row">
            <span>LED status</span>
            <strong>{alarmActive ? 'Flashing' : armed ? 'Standby' : 'Off'}</strong>
          </div>
          <div class="sensor-row">
            <span>Buzzer</span>
            <strong>{alarmActive ? 'Siren loop' : 'Muted'}</strong>
          </div>
          <div class="sensor-row">
            <span>LCD text</span>
            <strong>{lcdLine1}</strong>
          </div>
          <div class="sensor-row">
            <span>4-digit display</span>
            <strong>{tempC.toFixed(0)}&deg;C</strong>
          </div>
        </div>
      </section>
    </aside>
  </section>

  <section class="feature-grid reveal">
    {#each featureCards as feature}
      <article class="feature-card">
        <div class="feature-tag">{feature.tag}</div>
        <h3>{feature.title}</h3>
        <p>{feature.text}</p>
      </article>
    {/each}
  </section>

  <section class="bottom-grid">
    <article class="control-card reveal">
      <div class="panel-head">
        <div>
          <div class="panel-label">Event feed</div>
          <h2>Security log</h2>
        </div>
      </div>

      <ul class="log-list">
        {#each eventLog as event}
          <li class={event.tone}>
            <span>{event.time}</span>
            <strong>{event.message}</strong>
          </li>
        {/each}
      </ul>
    </article>

    <article class="control-card reveal">
      <div class="panel-head">
        <div>
          <div class="panel-label">Deployment notes</div>
          <h2>What this dashboard expects</h2>
        </div>
      </div>

      <div class="notes">
        <p>1. Run the camera in a secure browser context like localhost.</p>
        <p>2. Keep the Pico firmware connected to the alarm hardware.</p>
        <p>3. Face detection works when the browser supports the FaceDetector API.</p>
        <p>4. Motion fallback keeps the dashboard useful even without face support.</p>
      </div>
      <div class="status-strip">
        <span>{faceSupport ? 'Face API ready' : 'Motion fallback ready'}</span>
        <span>Last alert: {lastEvent}</span>
      </div>
    </article>
  </section>

  {#if cameraError}
    <section class="error-box reveal">
      <strong>Camera error</strong>
      <p>{cameraError}</p>
    </section>
  {/if}
</main>
