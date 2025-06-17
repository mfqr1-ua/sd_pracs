import pygame
import json

# Tamaño de cada celda en píxeles
CELL_SIZE = 30

class MapaCiudad:
    FILAS = 20
    COLUMNAS = 20

    def __init__(self):
        self.mapa = [[' ' for _ in range(self.COLUMNAS)] for _ in range(self.FILAS)]
        self.localizaciones = []  # Guardar localizaciones con posiciones y IDs
        self.taxis = []  # Guardar taxis con posiciones y IDs

    def agregar_localizacion(self, fila, columna, id_localizacion):
        self.mapa[fila][columna] = id_localizacion
        self.localizaciones.append((fila, columna, id_localizacion))  # Guardar para mostrar

    def agregar_taxi(self, fila, columna, id_taxi):
        self.taxis.append((fila, columna, id_taxi))  # Guardar para mostrar

    def cargar_localizaciones(self, archivo):
        with open(archivo) as f:
            data = json.load(f)
            for loc in data["locations"]:
                pos = loc["POS"].split(",")
                x, y = int(pos[0]), int(pos[1])
                self.agregar_localizacion(x, y, loc["Id"])

    def cargar_taxis(self, archivo):
        with open(archivo) as f:
            data = json.load(f)
            for taxi in data["taxis"]:
                self.agregar_taxi(0, 0, taxi["Id"])  # Todos los taxis empiezan en (0,0)

    def mostrar_mapa(self):
        pygame.init()
        screen = pygame.display.set_mode((self.COLUMNAS * CELL_SIZE, self.FILAS * CELL_SIZE))
        pygame.display.set_caption("Mapa de la Ciudad")

        # Configuración de la fuente para mostrar texto
        font = pygame.font.Font(None, 18)  # Ajusta el tamaño de la fuente si es necesario

        clock = pygame.time.Clock()
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

            screen.fill((255, 255, 255))  # Fondo blanco

            # Dibujar el mapa
            for fila in range(self.FILAS):
                for columna in range(self.COLUMNAS):
                    color = (200, 200, 200) if self.mapa[fila][columna] == ' ' else (0, 100, 255)
                    pygame.draw.rect(screen, color, (columna * CELL_SIZE, fila * CELL_SIZE, CELL_SIZE, CELL_SIZE), 0)
                    
                    # Dibujar texto de localizaciones si está presente
                    for loc_fila, loc_col, loc_id in self.localizaciones:
                        if loc_fila == fila and loc_col == columna:
                            text_surface = font.render(loc_id, True, (0, 0, 0))
                            screen.blit(text_surface, (columna * CELL_SIZE + 5, fila * CELL_SIZE + 5))

            # Dibujar los taxis como cuadrados
            for fila, columna, id_taxi in self.taxis:
                taxi_color = (255, 0, 0)
                pygame.draw.rect(screen, taxi_color, (columna * CELL_SIZE, fila * CELL_SIZE, CELL_SIZE, CELL_SIZE))
                text_surface = font.render(id_taxi, True, (255, 255, 255))
                screen.blit(text_surface, (columna * CELL_SIZE + 5, fila * CELL_SIZE + 5))

            pygame.display.flip()
            clock.tick(10)

        pygame.quit()

# Uso del MapaCiudad en Python
if __name__ == "__main__":
    ciudad = MapaCiudad()
    ciudad.cargar_localizaciones("EC_locations.json")
    ciudad.cargar_taxis("taxis.json")
    ciudad.mostrar_mapa()
