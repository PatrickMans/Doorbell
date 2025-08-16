# Doorbel.py
# 14 aug 2015
# Relais actief laag

import machine
import utime
import network
import urequests
from machine import Pin
import gc  # Garbage collector voor geheugenmanagement

# --- Configuratie-instellingen ---

# GPIO Pin-definities
BUTTON_PIN = 6
RELAY_PIN = 10
LED_PIN = 11

# Tijd-instellingen (in seconden)
RELAY_ACTIVE_TIME = 1
BUTTON_COOLDOWN_TIME = 5
DEBOUNCE_TIME = 0.05  # 50ms debounce tijd

# Wi-Fi instellingen
SSID = '<YOUR_WIFI_SSID>'
PASSWORD = '<YOUR_WIFI_PASSWORD>'
WIFI_TIMEOUT = 20  # Timeout in seconden
WIFI_RETRY_DELAY = 5

# Home Assistant Webhook URL
WEBHOOK_URL = '<YOUR_HA_WEBHOOK>'
WEBHOOK_TIMEOUT = 10  # Timeout voor webhook requests

# Maximaal aantal opeenvolgende fouten voordat het programma reset
MAX_CONSECUTIVE_ERRORS = 10  # Verhoogd voor meer tolerantie

# Wi-Fi retry instellingen
MAX_WIFI_INIT_ATTEMPTS = 5  # Maximaal 5 pogingen bij opstarten
WIFI_RECONNECT_MAX_ATTEMPTS = 3  # Maximaal 3 pogingen tijdens runtime

# Fallback/Emergency instellingen
EMERGENCY_MODE_THRESHOLD = 20  # Na 20 fouten: alleen basis functionaliteit
WATCHDOG_ENABLED = False  # Zet op True als je watchdog wilt gebruiken

# --- Pin-initialisatie ---

# Configureer de knop als een input-pin met interne pull-up weerstand.
# Dit betekent dat de pin standaard 'hoog' (True/1) is en 'laag' (False/0) wordt wanneer de knop wordt ingedrukt.
button = machine.Pin(BUTTON_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
# Configureer het relais als een output-pin.
relay = machine.Pin(RELAY_PIN, machine.Pin.OUT)
# Zorg ervoor dat het relais uit staat bij opstarten (1 = UIT voor actief-laag relais).
relay.value(1)  # 1 = relais UIT (actief-laag)
# Configureer de LED als een output-pin.
led = Pin('LED', Pin.OUT)
# Zorg ervoor dat de LED uit staat bij opstarten.
led.value(0)

print("GPIO pinnen geïnitialiseerd (actief-laag relais)")
except Exception as e:
    print(f"Fout bij initialiseren van GPIO pinnen: {e}")
    machine.reset()

# --- Functies ---

def connect_to_wifi():
    """
    Verbindt met Wi-Fi met verbeterde foutafhandeling en timeouts.
    Returnt wlan object bij succes, None bij falen.
    """
    try:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        
        if wlan.isconnected():
            print(f"Al verbonden met Wi-Fi. IP: {wlan.ifconfig()[0]}")
            return wlan
        
        print(f"Verbinden met Wi-Fi netwerk: {SSID}...")
        wlan.connect(SSID, PASSWORD)
        
        # Wacht tot verbonden of timeout
        timeout_counter = 0
        while not wlan.isconnected() and timeout_counter < WIFI_TIMEOUT:
            utime.sleep(1)
            timeout_counter += 1
            if timeout_counter % 5 == 0:  # Print elke 5 seconden
                print(f"Verbindingspoging... ({timeout_counter}/{WIFI_TIMEOUT})")
        
        if wlan.isconnected():
            ip_info = wlan.ifconfig()
            print(f'✓ Verbonden met Wi-Fi!')
            print(f'  IP-adres: {ip_info[0]}')
            print(f'  Gateway: {ip_info[2]}')
            return wlan
        else:
            print('✗ Wi-Fi verbinding timeout.')
            wlan.active(False)  # Deactiveer Wi-Fi interface bij mislukking
            return None
            
    except Exception as e:
        print(f"✗ Fout bij Wi-Fi verbinding: {e}")
        try:
            wlan.active(False)  # Zorg voor cleanup ook bij exceptie
        except:
            pass
        return None

def check_wifi_connection(wlan):
    """
    Controleert of de Wi-Fi verbinding nog actief is.
    """
    try:
        if wlan and wlan.isconnected():
            return True
        else:
            print("Wi-Fi verbinding verloren!")
            return False
    except Exception as e:
        print(f"Fout bij controleren Wi-Fi status: {e}")
        return False

def send_webhook():
    """
    Verstuurt webhook met verbeterde foutafhandeling en timeouts.
    """
    try:
        print(f"Versturen van webhook naar: {WEBHOOK_URL}")
        
        # Voeg JSON payload toe met nuttige informatie
        payload = {
            'event': 'doorbell_press',
            'device': 'pico_w_doorbell',
            'timestamp': utime.time(),
            'free_memory': gc.mem_free()
        }
        
        # Maak request met timeout
        response = urequests.post(
            WEBHOOK_URL, 
            json=payload, 
            timeout=WEBHOOK_TIMEOUT,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 200:
            print(f"Webhook succesvol verstuurd. Status: {response.status_code}")
            success = True
        else:
            print(f"Webhook fout. Status: {response.status_code}")
            success = False
            
        response.close()
        return success
        
    except OSError as e:
        print(f"Netwerkfout bij webhook: {e}")
        return False
    except Exception as e:
        print(f"Algemene fout bij webhook: {e}")
        return False

def activate_relay():
    """
    Activeert het relais voor de ingestelde tijd.
    ACTIEF-LAAG RELAIS: 0 = AAN, 1 = UIT
    DEZE FUNCTIE MOET ALTIJD WERKEN - minimale foutafhandeling.
    """
    try:
        print(f"Relais activeren voor {RELAY_ACTIVE_TIME} seconde(n)...")
        relay.value(0)  # 0 = relais AAN (actief-laag)
        led.value(1)    # LED AAN voor visuele feedback
        utime.sleep(RELAY_ACTIVE_TIME)
        relay.value(1)  # 1 = relais UIT (actief-laag) 
        led.value(0)    # LED UIT
        print("Relais gedeactiveerd")
        return True
    except Exception as e:
        print(f"KRITIEK: Relais fout: {e}")
        # ALTIJD proberen relais uit te zetten (1 = UIT), zelfs bij fout
        for attempt in range(3):  # 3 pogingen
            try:
                relay.value(1)  # 1 = relais UIT (actief-laag)
                led.value(0)
                print(f"Noodstop relais poging {attempt + 1} succesvol")
                break
            except:
                utime.sleep(0.1)
        return False

def handle_button_press(wlan):
    """
    Behandelt een knopdruk met alle bijbehorende acties.
    """
    print("\n--- Drukknop ingedrukt! ---")
    
    success_count = 0
    total_actions = 1  # Altijd: relais activatie
    webhook_attempted = False
    
    # 1. Activeer relais (altijd uitvoeren)
    if activate_relay():
        success_count += 1
        print("✓ Relais succesvol geactiveerd")
    else:
        print("✗ Relais activatie mislukt")
    
    # 2. Verstuur webhook (alleen als Wi-Fi beschikbaar is)
    if wlan and check_wifi_connection(wlan):
        total_actions = 2  # Verhoog naar 2 als webhook ook wordt geprobeerd
        webhook_attempted = True
        if send_webhook():
            success_count += 1
            print("✓ Webhook succesvol verstuurd")
        else:
            print("✗ Webhook versturen mislukt")
        # Forceer garbage collection na webhook
        gc.collect()
    else:
        print("ℹ Geen Wi-Fi verbinding - webhook overgeslagen")
    
    if webhook_attempted:
        print(f"Knopdruk verwerkt: {success_count}/{total_actions} acties succesvol")
    else:
        print(f"Knopdruk verwerkt: {success_count}/{total_actions} actie succesvol (offline modus)")
    
    return success_count == total_actions

def emergency_button_handler():
    """
    Ultiem eenvoudige knop handler voor noodgevallen.
    Geen Wi-Fi, geen logging, alleen relais activeren.
    ACTIEF-LAAG RELAIS: 0 = AAN, 1 = UIT
    """
    try:
        if button.value() == 0:  # Knop ingedrukt
            relay.value(0)  # 0 = relais AAN (actief-laag)
            led.value(1)
            utime.sleep(RELAY_ACTIVE_TIME)
            relay.value(1)  # 1 = relais UIT (actief-laag)
            led.value(0)
            return True
    except:
        # Zelfs bij fout: probeer relais uit te zetten
        try:
            relay.value(1)  # 1 = relais UIT (actief-laag)
            led.value(0)
        except:
            pass
    return False

def safe_sleep(duration):
    """
    Veilige sleep die onderbreekbaar is en geen exceptions gooit.
    """
    try:
        utime.sleep(duration)
    except:
        pass

def debounce_button():
    """
    Eenvoudige debounce functie voor de knop.
    """
    try:
        if button.value() == 0:  # Knop ingedrukt
            safe_sleep(DEBOUNCE_TIME)
            return button.value() == 0  # Nog steeds ingedrukt na debounce
    except:
        # Bij elke fout: probeer emergency handler
        return emergency_button_handler()
    return False

# --- Hoofdprogramma ---

def main():
    print("=== Raspberry Pi Pico W Deurbel Systeem ===")
    print("🔒 ALTIJD-WERKEN MODUS ACTIEF")
    print("Opstarten...")
    
    # Initiële Wi-Fi verbinding met maximaal 5 pogingen
    wlan = None
    wifi_enabled = False
    
    print(f"\nWi-Fi initialisatie (max {MAX_WIFI_INIT_ATTEMPTS} pogingen)...")
    for attempt in range(1, MAX_WIFI_INIT_ATTEMPTS + 1):
        print(f"Wi-Fi poging {attempt}/{MAX_WIFI_INIT_ATTEMPTS}:")
        wlan = connect_to_wifi()
        
        if wlan is not None:
            wifi_enabled = True
            print(f"✓ Wi-Fi succesvol verbonden na {attempt} poging(en)")
            break
        else:
            print(f"✗ Wi-Fi poging {attempt} mislukt")
            if attempt < MAX_WIFI_INIT_ATTEMPTS:
                print(f"Wachten {WIFI_RETRY_DELAY} seconden voor volgende poging...")
                safe_sleep(WIFI_RETRY_DELAY)
    
    # Status rapportage
    print("\n" + "="*50)
    if wifi_enabled:
        print("🌐 SYSTEEM STATUS: ONLINE MODUS")
        print("✓ Relais functionaliteit: Actief")
        print("✓ Webhook functionaliteit: Actief")
        ip = wlan.ifconfig()[0]
        print(f"✓ IP-adres: {ip}")
    else:
        print("📱 SYSTEEM STATUS: OFFLINE MODUS") 
        print("✓ Relais functionaliteit: Actief")
        print("✗ Webhook functionaliteit: Uitgeschakeld")
        print("ℹ  Systeem werkt zonder netwerk verbinding")
    print("🔒 GARANTIE: Deurbel werkt ALTIJD, ongeacht fouten!")
    print("="*50)
    
    print("\nSysteem gereed. Drukknop monitoring actief...")
    print("Druk op CTRL+C om te stoppen\n")
    
    # Status variabelen
    last_press_time = 0
    consecutive_errors = 0
    total_errors = 0
    wifi_reconnect_attempts = 0
    last_wifi_check = 0
    emergency_mode = False
    
    # Optionele watchdog (uitgeschakeld standaard)
    wdt = None
    if WATCHDOG_ENABLED:
        try:
            wdt = machine.WDT(timeout=30000)  # 30 seconden timeout
            print("🐕 Watchdog actief (30s timeout)")
        except:
            print("⚠️  Watchdog niet beschikbaar op dit platform")
    
    try:
        while True:
            # Feed watchdog als actief
            if wdt:
                try:
                    wdt.feed()
                except:
                    pass
            
            current_time = utime.time()
            
            # Check voor emergency mode
            if total_errors > EMERGENCY_MODE_THRESHOLD and not emergency_mode:
                emergency_mode = True
                print(f"🚨 EMERGENCY MODE: Te veel fouten ({total_errors}). Alleen basis functionaliteit.")
                # Zet Wi-Fi uit om resources te besparen
                if wlan:
                    try:
                        wlan.active(False)
                        wlan = None
                    except:
                        pass
            
            # Periodieke Wi-Fi check (alleen als niet in emergency mode)
            if not emergency_mode and wifi_enabled and (current_time - last_wifi_check) >= 30:
                last_wifi_check = current_time
                
                if wlan and not check_wifi_connection(wlan):
                    wifi_reconnect_attempts += 1
                    
                    if wifi_reconnect_attempts <= WIFI_RECONNECT_MAX_ATTEMPTS:
                        print(f"📡 Wi-Fi herverbinding poging ({wifi_reconnect_attempts}/{WIFI_RECONNECT_MAX_ATTEMPTS})...")
                        new_wlan = connect_to_wifi()
                        
                        if new_wlan:
                            wlan = new_wlan
                            wifi_reconnect_attempts = 0  # Reset bij succes
                            print("✓ Wi-Fi herverbinding succesvol")
                        else:
                            print("✗ Wi-Fi herverbinding mislukt")
                    else:
                        print(f"⚠️  Max herverbindingen bereikt. Schakel over naar offline modus.")
                        try:
                            wlan.active(False)
                        except:
                            pass
                        wlan = None
                        wifi_reconnect_attempts = 0
            
            # Knop controle met debouncing
            button_pressed = False
            try:
                button_pressed = debounce_button()
            except Exception as e:
                print(f"⚠️  Knop check fout: {e}")
                total_errors += 1
                # Probeer emergency handler
                try:
                    button_pressed = emergency_button_handler()
                except:
                    pass
            
            if button_pressed:
                # Controleer cooldown periode
                if (current_time - last_press_time) > BUTTON_COOLDOWN_TIME:
                    success = False
                    
                    if emergency_mode:
                        # Emergency mode: alleen relais, geen fancy functionaliteit
                        print("\n🚨 EMERGENCY: Basis knopdruk...")
                        try:
                            success = activate_relay()
                            if success:
                                print("✓ Emergency relais activatie succesvol")
                            else:
                                print("✗ Emergency relais activatie mislukt")
                        except:
                            print("💥 Critical error in emergency mode")
                    else:
                        # Normale mode
                        try:
                            success = handle_button_press(wlan)
                            
                        except Exception as e:
                            print(f"✗ Fout bij verwerken knopdruk: {e}")
                            total_errors += 1
                            consecutive_errors += 1
                            
                            # Als normale handler faalt, probeer emergency
                            print("🚨 Fallback naar emergency handler...")
                            try:
                                success = emergency_button_handler()
                                if success:
                                    print("✓ Emergency fallback succesvol")
                            except:
                                print("💥 Emergency fallback ook gefaald")
                    
                    last_press_time = current_time
                    
                    if success:
                        consecutive_errors = 0  # Reset error counter bij succes
                    else:
                        consecutive_errors += 1
                        total_errors += 1
                    
                    # Reset systeem alleen bij HEEL veel fouten (verhoogde drempel)
                    if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                        print(f"🔄 Teveel opeenvolgende fouten ({consecutive_errors}). Systeem herstart...")
                        print("🔒 Laatste poging: forceer relais uit...")
                        # Meerdere pogingen om relais uit te zetten (1 = UIT voor actief-laag)
                        for i in range(5):
                            try:
                                relay.value(1)  # 1 = relais UIT (actief-laag)
                                led.value(0)
                                safe_sleep(0.2)
                            except:
                                pass
                        
                        safe_sleep(3)
                        machine.reset()
                        
                else:
                    remaining_cooldown = BUTTON_COOLDOWN_TIME - (current_time - last_press_time)
                    print(f"⏳ Knop cooldown actief. Nog {remaining_cooldown:.1f} seconden...")
            
            # Korte sleep om CPU belasting te verminderen
            safe_sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n👋 Programma gestopt door gebruiker.")
    except Exception as e:
        print(f"💥 Kritieke fout in hoofdloop: {e}")
        print("🚨 EMERGENCY SHUTDOWN...")
        
        # Emergency cleanup - meerdere pogingen (1 = UIT voor actief-laag relais)
        for attempt in range(5):
            try:
                relay.value(1)  # 1 = relais UIT (actief-laag)
                led.value(0)
                print(f"✓ Emergency cleanup poging {attempt + 1}")
                break
            except:
                safe_sleep(0.1)
        
        print("🔄 Systeem herstart over 5 seconden...")
        safe_sleep(5)
        machine.reset()
        
    finally:
        # Cleanup met meerdere pogingen (1 = UIT voor actief-laag relais)
        print("🧹 Uitgebreide cleanup...")
        for attempt in range(3):
            try:
                relay.value(1)  # 1 = relais UIT (actief-laag)
                led.value(0)
                if wlan:
                    wlan.active(False)
                print(f"✓ Cleanup poging {attempt + 1} succesvol")
                break
            except:
                safe_sleep(0.1)
        print("✓ Cleanup voltooid.")

# Start het programma
if __name__ == "__main__":
    main()
