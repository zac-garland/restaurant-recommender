// Restaurant Recommender Frontend Script

let map;
let markers = [];
let userLocation = null;
let userMarker = null;
let locationGranted = false;
let mapInitialized = false;

document.addEventListener('DOMContentLoaded', function() {
    setupLandingPage();
});

function setupLandingPage() {
    const landingLocationBtn = document.getElementById('landing-location-btn');
    const landingSearchInput = document.getElementById('landing-search-input');
    
    // Handle location button on landing page
    landingLocationBtn.addEventListener('click', function() {
        getLandingLocation();
    });
    
    // Handle Enter key on landing search
    landingSearchInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            const query = landingSearchInput.value.trim();
            if (query) {
                transitionToMainApp(query);
            }
        }
    });
}

function getLandingLocation() {
    const btn = document.getElementById('landing-location-btn');
    
    if (navigator.geolocation) {
        btn.textContent = '⏳ Getting location...';
        
        navigator.geolocation.getCurrentPosition(
            function(position) {
                userLocation = {
                    lat: position.coords.latitude,
                    lng: position.coords.longitude
                };
                
                locationGranted = true;
                btn.textContent = '✓ Location Granted!';
                btn.classList.add('granted');
                
                setTimeout(() => {
                    document.getElementById('landing-search-input').focus();
                }, 500);
            },
            function(error) {
                console.error('Geolocation error:', error);
                btn.textContent = '📍 Grant Location Access';
                alert('Unable to get your location. You can still search, but results won\'t be distance-filtered.');
            }
        );
    } else {
        alert('Geolocation is not supported by this browser.');
    }
}

function transitionToMainApp(initialQuery = '') {
    // Slide out landing page
    const landingPage = document.getElementById('landing-page');
    const mainApp = document.getElementById('main-app');
    
    landingPage.classList.add('slide-out');
    
    // Wait for slide animation, then show main app
    setTimeout(() => {
        landingPage.style.display = 'none';
        mainApp.classList.add('slide-in');
        
        // Initialize map only once we transition
        if (!mapInitialized) {
            initializeMap();
            setupEventListeners();
            mapInitialized = true;
        }
        
        // If we have a query, perform the search
        if (initialQuery) {
            document.getElementById('search-input').value = initialQuery;
            setTimeout(() => {
                performSearch();
            }, 500);
        }
        
        // If location was granted, show it on the map
        if (locationGranted && userLocation) {
            addUserLocationMarker();
        }
    }, 800);
}

function initializeMap() {
    map = L.map('map').setView([30.2672, -97.7431], 13); // Austin coordinates

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);
}

function setupEventListeners() {
    document.getElementById('search-btn').addEventListener('click', performSearch);
    document.getElementById('location-btn').addEventListener('click', getUserLocation);
    document.getElementById('search-input').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            performSearch();
        }
    });

    // Tab switching
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            switchTab(this.dataset.tab);
        });
    });
}

function addUserLocationMarker() {
    if (!userLocation) return;
    
    // Remove old user marker if exists
    if (userMarker) {
        map.removeLayer(userMarker);
    }
    
    // Add blue marker for user location
    const blueIcon = L.icon({
        iconUrl: 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPGNpcmNsZSBjeD0iMTIiIGN5PSIxMiIgcj0iOCIgZmlsbD0iIzIzNjNlYiIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIzIi8+Cjwvc3ZnPg==',
        iconSize: [24, 24],
        iconAnchor: [12, 12],
        popupAnchor: [0, -12]
    });
    
    userMarker = L.marker([userLocation.lat, userLocation.lng], {icon: blueIcon})
        .addTo(map)
        .bindPopup('<b>Your Location</b>')
        .openPopup();
        
    map.setView([userLocation.lat, userLocation.lng], 13);
}

async function performSearch() {
    const query = document.getElementById('search-input').value.trim();
    if (!query) return;

    const radius = parseFloat(document.getElementById('radius-select').value);
    const maxPrice = parseInt(document.getElementById('price-select').value);

    try {
        const response = await fetch('http://localhost:8001/search', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                query: query,
                user_lat: userLocation ? userLocation.lat : null,
                user_lng: userLocation ? userLocation.lng : null,
                radius: radius,
                max_price: maxPrice
            })
        });

        if (!response.ok) {
            throw new Error('Search failed');
        }

        const results = await response.json();
        displayResults(results);
        switchTab('map'); // Auto-navigate to map
    } catch (error) {
        console.error('Search error:', error);
        alert('Search failed. Please try again.');
    }
}

function displayResults(restaurants) {
    // Clear previous markers
    markers.forEach(marker => map.removeLayer(marker));
    markers = [];

    // Clear list
    const listContainer = document.getElementById('results-list');
    listContainer.innerHTML = '';

    if (restaurants.length === 0) {
        listContainer.innerHTML = '<p>No restaurants found matching your criteria.</p>';
        return;
    }

        // Add markers to map and items to list
    restaurants.forEach(restaurant => {
        // Add marker - use lat/lng or latitude/longitude
        const lat = restaurant.latitude || restaurant.lat;
        const lng = restaurant.longitude || restaurant.lng;
        
        if (lat && lng) {
            // Create popup content with reviews/topics/tags
            const popupContent = `
                <div style="max-width: 300px;">
                    <h3 style="margin: 0 0 10px 0;">${restaurant.name}</h3>
                    <p><strong>Rating:</strong> ${restaurant.rating || 'N/A'} ⭐ (${restaurant.user_ratings_total || 0} reviews)</p>
                    <p><strong>Price:</strong> ${'$'.repeat(restaurant.price_level || 1)}</p>
                    <p><strong>Distance:</strong> ${restaurant.distance ? restaurant.distance.toFixed(2) + ' miles' : 'N/A'}</p>
                    <p><strong>Match Score:</strong> ${restaurant.similarity ? (restaurant.similarity * 100).toFixed(1) + '%' : 'N/A'}</p>
                    ${restaurant.place_tags ? `<p><strong>Tags:</strong> ${restaurant.place_tags.split(',').slice(0, 5).join(', ')}</p>` : ''}
                    ${restaurant.top_review ? `<p style="font-style: italic; margin-top: 10px;">"${restaurant.top_review}"</p>` : ''}
                    <p style="margin-top: 10px; font-size: 0.9em;">${restaurant.address || ''}</p>
                </div>
            `;
            
            const marker = L.marker([lat, lng])
                .addTo(map)
                .bindPopup(popupContent);
            markers.push(marker);
        }

        // Add to list
        const card = document.createElement('div');
        card.className = 'restaurant-card';
        card.innerHTML = `
            <h3>${restaurant.name}</h3>
            <p><strong>Price Level:</strong> ${'$'.repeat(restaurant.price_level || 1)}</p>
            <p><strong>Rating:</strong> ${restaurant.rating || 'N/A'} ⭐ (${restaurant.user_ratings_total || 0} reviews)</p>
            <p><strong>Distance:</strong> ${restaurant.distance ? restaurant.distance.toFixed(2) + ' miles' : 'N/A'}</p>
            <p><strong>Address:</strong> ${restaurant.address || 'N/A'}</p>
            <p><strong>Similarity:</strong> ${restaurant.similarity ? (restaurant.similarity * 100).toFixed(1) + '%' : 'N/A'}</p>
            ${restaurant.place_tags ? `<p><strong>Categories:</strong> ${restaurant.place_tags.split(',').slice(0, 5).join(', ')}</p>` : ''}
        `;
        
        // Click card to show marker popup
        card.addEventListener('click', () => {
            marker.openPopup();
            map.setView([lat, lng], 15);
            switchTab('map');
        });
        
        listContainer.appendChild(card);
    });

    // Fit map to markers
    if (markers.length > 0) {
        const group = new L.featureGroup(markers);
        map.fitBounds(group.getBounds().pad(0.1));
    }
}

function getUserLocation() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            function(position) {
                userLocation = {
                    lat: position.coords.latitude,
                    lng: position.coords.longitude
                };
                
                locationGranted = true;
                addUserLocationMarker();
                
                alert('Location obtained! Your searches will now consider proximity.');
            },
            function(error) {
                console.error('Geolocation error:', error);
                alert('Unable to get your location. Please check your browser settings.');
            }
        );
    } else {
        alert('Geolocation is not supported by this browser.');
    }
}

function switchTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    // Show selected tab
    document.getElementById(tabName + '-tab').classList.add('active');
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
}