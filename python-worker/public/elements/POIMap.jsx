import { useEffect, useRef, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { MapPin, Star } from 'lucide-react';

export default function POIMap() {
    const mapRef = useRef(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        // Load Google Maps API
        const loadGoogleMaps = () => {
            if (window.google && window.google.maps) {
                initMap();
                return;
            }

            const script = document.createElement('script');
            script.src = `https://maps.googleapis.com/maps/api/js?key=${props.apiKey}&callback=initGoogleMap`;
            script.async = true;
            script.defer = true;
            
            window.initGoogleMap = () => {
                initMap();
            };

            script.onerror = () => {
                setError('Failed to load Google Maps');
                setLoading(false);
            };

            document.head.appendChild(script);
        };

        const initMap = () => {
            const pois = props.pois || [];
            
            if (!pois.length || !mapRef.current) {
                setError('No POIs to display');
                setLoading(false);
                return;
            }

            try {
                // Create map centered on first POI
                const map = new window.google.maps.Map(mapRef.current, {
                    zoom: 13,
                    center: { lat: pois[0].lat, lng: pois[0].lng },
                    mapTypeControl: true,
                    streetViewControl: true,
                    fullscreenControl: true,
                    styles: [
                        {
                            featureType: "poi",
                            elementType: "labels",
                            stylers: [{ visibility: "off" }]
                        }
                    ]
                });

                const bounds = new window.google.maps.LatLngBounds();
                const infoWindow = new window.google.maps.InfoWindow();

                // Add markers for each POI
                pois.forEach((poi, index) => {
                    const position = { lat: poi.lat, lng: poi.lng };
                    
                    const marker = new window.google.maps.Marker({
                        position: position,
                        map: map,
                        title: poi.name,
                        label: {
                            text: String(index + 1),
                            color: 'white',
                            fontWeight: 'bold',
                            fontSize: '14px'
                        },
                        animation: window.google.maps.Animation.DROP
                    });

                    bounds.extend(position);

                    // Create info window content
                    const rating = poi.rating 
                        ? `⭐ ${poi.rating}/5 (${poi.user_ratings_total || 0} reviews)` 
                        : 'No rating available';
                    
                        const description = poi.description 
                            ? `<p style="margin: 8px 0; font-size: 13px; color: #3c4043;">${poi.description}</p>` 
                            : '';
                    
                    const url = poi.url 
                        ? `<p style="margin: 8px 0;"><a href="${poi.url}" target="_blank" rel="noopener noreferrer" style="color: #1a73e8; text-decoration: none;">View on Google Maps →</a></p>` 
                        : '';
                    
                    const photoHtml = poi.photo_url
                        ? `<img src="${poi.photo_url}" alt="${poi.name}" style="width: 100%; max-width: 250px; border-radius: 8px; margin: 8px 0;" />`
                        : '';
                    
                        const content = `
                            <div style="max-width: 280px; font-family: system-ui, -apple-system, sans-serif;">
                                <h3 style="margin: 0 0 8px 0; font-size: 16px; font-weight: 600; color: #202124;">${poi.name}</h3>
                                ${photoHtml}
                                <p style="margin: 4px 0; font-size: 13px; color: #f4b400; font-weight: bold;">${rating}</p>
                                <p style="margin: 4px 0; font-size: 12px; color: #5f6368;">${poi.address}</p>
                                ${description}
                                ${url}
                            </div>
                        `;

                    marker.addListener('click', () => {
                        infoWindow.setContent(content);
                        infoWindow.open(map, marker);
                    });
                });

                // Fit map to show all markers with padding
                if (pois.length > 1) {
                    map.fitBounds(bounds, {
                        padding: { top: 60, right: 60, bottom: 60, left: 60 }
                    });
                } else {
                    // Single POI - set appropriate zoom level
                    map.setZoom(15);
                }

                setLoading(false);
            } catch (err) {
                setError('Error initializing map: ' + err.message);
                setLoading(false);
            }
        };

        loadGoogleMaps();
    }, []);

    if (error) {
        return (
            <Card className="w-full">
                <CardContent className="pt-6">
                    <div className="text-center text-muted-foreground">
                        <MapPin className="h-8 w-8 mx-auto mb-2 opacity-50" />
                        <p>{error}</p>
                    </div>
                </CardContent>
            </Card>
        );
    }

    return (
        <Card className="w-full">
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-lg font-medium flex items-center gap-2">
                        <MapPin className="h-5 w-5" />
                        Points of Interest Map
                    </CardTitle>
                    {props.pois && (
                        <Badge variant="secondary">
                            {props.pois.length} {props.pois.length === 1 ? 'location' : 'locations'}
                        </Badge>
                    )}
                </div>
            </CardHeader>
            <CardContent>
                {loading && (
                    <div style={{ height: '500px', display: 'flex', alignItems: 'center', justifyContent: 'center' }} className="bg-muted rounded-md">
                        <div className="text-center">
                            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-2"></div>
                            <p className="text-sm text-muted-foreground">Loading map...</p>
                        </div>
                    </div>
                )}
                <div 
                    ref={mapRef} 
                    style={{ 
                        width: '100%', 
                        height: '500px',
                        minHeight: '500px',
                        display: loading ? 'none' : 'block'
                    }}
                    className="rounded-md border"
                />
            </CardContent>
        </Card>
    );
}

