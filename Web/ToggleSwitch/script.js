document.getElementById('addSwitchBtn').addEventListener('click', () => {
    const style = document.getElementById('switchStyle').value;
    const orientation = document.getElementById('switchOrientation').value;
    const positions = parseInt(document.getElementById('switchPositions').value);
    const travelPx = parseInt(document.getElementById('switchTravel').value);
    const labelText = document.getElementById('switchLabel').value;

    // 1. Map styles to classes based on your exact CSS
    let trackClass, leverClass, isTGGS1 = false,
        innerHTML = '';

    switch (style) {
        case 'tggs1-l1':
            trackClass = 'tggs1-hole';
            leverClass = 'tggs1-lever1';
            isTGGS1 = true;
            break;
        case 'tggs1-l2':
            trackClass = 'tggs1-hole';
            leverClass = 'tggs1-lever2';
            isTGGS1 = true;
            break;
        case 'tggs1-l3':
            trackClass = 'tggs1-hole';
            leverClass = 'tggs1-lever3';
            isTGGS1 = true;
            break;
        case 'tggs1-l4':
            trackClass = 'tggs1-hole';
            leverClass = 'tggs1-lever4';
            isTGGS1 = true;
            innerHTML = labelText.replace(' ', '<br>');
            break;

        case 'tggs2-t1':
            trackClass = 'tggs2-circle1';
            leverClass = 'tggs2-lever1';
            break;
        case 'tggs2-t2':
            trackClass = 'tggs2-circle2';
            leverClass = 'tggs2-lever2';
            break;
    }

    // 2. Build HTML
    const wrapper = document.createElement('div');
    wrapper.className = 'switch-wrapper';

    const info = document.createElement('div');
    info.className = 'switch-info';
    info.innerHTML = `${style}<br>${positions}-Way | ${travelPx}px travel`;

    let finalContainer;
    let trackContainer = document.createElement('div');
    trackContainer.className = `drag-track ${trackClass}`;

    const lever = document.createElement('div');
    lever.className = `drag-lever ${leverClass}`;
    lever.innerHTML = innerHTML;
    trackContainer.appendChild(lever);

    // If TGGS1, wrap in the static Outer and Inner circles
    if (isTGGS1) {
        const outerCircle = document.createElement('div');
        outerCircle.className = 'tggs1-circle';

        const innerCircle = document.createElement('div');
        innerCircle.className = 'tggs1-inner';

        innerCircle.appendChild(trackContainer);
        outerCircle.appendChild(innerCircle);
        finalContainer = outerCircle;
    } else {
        finalContainer = trackContainer;
    }

    wrapper.appendChild(info);
    wrapper.appendChild(finalContainer);
    document.getElementById('panelCanvas').appendChild(wrapper);

    // 3. Attach Drag Engine (Now with Scroll support!)
    attachDragLogic(trackContainer, lever, positions, orientation, travelPx);
});

// --- UPDATED DRAG & SCROLL ENGINE ---
function attachDragLogic(track, lever, totalSteps, orientation, travelPx) {
    let isDragging = false;
    let startY, startX, startTop, startLeft;
    let centerV = 0,
        centerH = 0;
    let currentStepIndex = 0; // Tracks the current active state state internally

    // Calculate the center point completely independent of outer borders
    function calculateCenters() {
        centerV = (track.clientHeight - lever.offsetHeight) / 2;
        centerH = (track.clientWidth - lever.offsetWidth) / 2;
    }

    function snapToStep(step) {
        calculateCenters();
        // Constrain step to valid steps array bounds
        currentStepIndex = Math.max(0, Math.min(step, totalSteps - 1));
        const ratio = totalSteps > 1 ? currentStepIndex / (totalSteps - 1) : 0;

        // Apply smooth transition when snapping via wheel or mouseup
        lever.style.transition = 'top 0.15s ease-out, left 0.15s ease-out';

        if (orientation === 'vertical') {
            lever.style.top = `${centerV - (travelPx / 2) + (ratio * travelPx)}px`;
            lever.style.left = `${centerH}px`;
        } else {
            lever.style.left = `${centerH - (travelPx / 2) + (ratio * travelPx)}px`;
            lever.style.top = `${centerV}px`;
        }
    }

    // Initialize position layout cleanly after DOM render
    setTimeout(() => snapToStep(0), 10);

    // --- MOUSE WHEEL LOGIC ---
    track.addEventListener('wheel', (e) => {
        e.preventDefault(); // Stop the main web browser window from scrolling up/down

        if (e.deltaY < 0) {
            // Scroll Up -> Move lever Up or Left (Decrease state index)
            if (currentStepIndex > 0) {
                snapToStep(currentStepIndex - 1);
            }
        } else if (e.deltaY > 0) {
            // Scroll Down -> Move lever Down or Right (Increase state index)
            if (currentStepIndex < totalSteps - 1) {
                snapToStep(currentStepIndex + 1);
            }
        }
    }, { passive: false }); // passive: false is mandatory to allow e.preventDefault()

    // --- DRAG LOGIC ---
    lever.addEventListener('mousedown', (e) => {
        isDragging = true;
        lever.style.transition = 'none'; // Kill transitions during active dragging
        calculateCenters();
        startY = e.clientY;
        startX = e.clientX;
        startTop = parseFloat(lever.style.top) || 0;
        startLeft = parseFloat(lever.style.left) || 0;
    });

    window.addEventListener('mousemove', (e) => {
        if (!isDragging) return;

        const minTravel = -(travelPx / 2);
        const maxTravel = (travelPx / 2);

        if (orientation === 'vertical') {
            let newTop = startTop + (e.clientY - startY);
            newTop = Math.max(centerV + minTravel, Math.min(newTop, centerV + maxTravel));
            lever.style.top = `${newTop}px`;
        } else {
            let newLeft = startLeft + (e.clientX - startX);
            newLeft = Math.max(centerH + minTravel, Math.min(newLeft, centerH + maxTravel));
            lever.style.left = `${newLeft}px`;
        }
    });

    window.addEventListener('mouseup', () => {
        if (!isDragging) return;
        isDragging = false;

        calculateCenters();

        let ratio;
        if (orientation === 'vertical') {
            const currentOffset = parseFloat(lever.style.top) - (centerV - (travelPx / 2));
            ratio = currentOffset / travelPx;
        } else {
            const currentOffset = parseFloat(lever.style.left) - (centerH - (travelPx / 2));
            ratio = currentOffset / travelPx;
        }

        const calculatedStep = Math.round(ratio * (totalSteps - 1));
        snapToStep(calculatedStep);
    });
}