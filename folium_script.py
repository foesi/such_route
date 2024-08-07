import pandas as pd
import folium
import seaborn as sns


class FoliumMap():
    def __init__(self, csv_file):
        self.data = pd.read_csv(csv_file, delimiter=';')

    def create_map(self, output_file="swiss_cantons_map.html"):
        # Husl generates evenly spaced colors
        palette = sns.color_palette("husl", 9).as_hex()

        foliumColors = ['blue', 'darkgreen', 'cadetblue', 'lightgray', 'purple', 'orange',
                        'darkred', 'lightblue', 'darkblue', 'darkpurple', 'pink', 'black', 'green', 'red']

        # Initialize the Folium map
        center_lat = self.data['Latitude'].mean()
        center_lng = self.data['Longitude'].mean()
        mymap = folium.Map(location=[center_lat, center_lng], zoom_start=8)

        # Add points to the map
        for index, row in self.data.iterrows():
            folium.Marker(
                location=[row['Latitude'], row['Longitude']],
                popup=f"{row['Canton']}<br>Comment: {row['Comment']}<br>Order: {row['Order']}",
                # , icon="info-sign", icon_color=]
                icon=folium.Icon(color=foliumColors[row['Group']])
                # folium.CircleMarker(
                #     location=[row['Latitude'], row['Longitude']],
                #     radius=10,
                #     popup=f"{row['Canton']}<br>Comment: {row['Comment']}<br>Order: {row['Order']}",
                #     color=palette[row['Group']],           # Border color
                #     fill=True,
                #     fill_color=palette[row['Group']],      # Fill color
                #     fill_opacity=0.7
            ).add_to(mymap)

        route = []
        for index, row in self.data.iterrows():
            route.append((index, row['Order']))

        route.sort(key=lambda x: x[1])

        route_coords = []
        check_route = []
        for i in range(len(route)-1):
            cur = route[i][0]
            nex = route[i+1][0]
            check_route.append((cur, nex))
            route_coords.append([(self.data['Latitude'][cur], self.data['Longitude'][cur]), (
                self.data['Latitude'][nex], self.data['Longitude'][nex])])

        folium.PolyLine(
            locations=route_coords,
            color="blue",
            opacity=1,
            smooth_factor=0,
        ).add_to(mymap)

        # Save the map to an HTML file
        mymap.save(output_file)

if __name__ == "__main__":
    map = FoliumMap("checkpoints_ordered.csv")
    map.create_map()