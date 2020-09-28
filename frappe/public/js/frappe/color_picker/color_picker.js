import utils from './utils';

class Picker {
	constructor(opts) {
		this.parent = opts.parent;
		this.width = opts.width;
		this.height = opts.height;
		this.color = opts.color;
		this.swatches = opts.swatches;
		this.setup_picker();
	}

	setup_picker() {
		let color_picker_template = document.createElement('template');
		color_picker_template.innerHTML = `
			<div class="color-picker">
				RECENT <br>
				<div class="swatches"></div>
				COLOR PICKER <br>
				<div class="color-map">
					<div class="color-selector"></div>
				</div>
				<div class="hue-map">
					<div class="hue-selector"></div>
				</div>
			</div>
		`.trim();
		this.color_picker_wrapper = color_picker_template.content.firstElementChild.cloneNode(true);
		this.parent.appendChild(this.color_picker_wrapper);
		this.color_map = this.color_picker_wrapper.getElementsByClassName('color-map')[0];
		this.color_selector_circle = this.color_map.getElementsByClassName('color-selector')[0];
		this.hue_map = this.color_picker_wrapper.getElementsByClassName('hue-map')[0];
		this.swatches_wrapper = this.color_picker_wrapper.getElementsByClassName('swatches')[0];
		this.hue_selector_circle = this.hue_map.getElementsByClassName('hue-selector')[0];
		this.set_selector_position();
		this.setup_events();
		this.setup_swatches();
		this.update_color_map();
	}

	setup_events() {
		this.setup_hue_event();
		this.setup_color_event();
	}

	setup_swatches() {
		let swatch_template = document.createElement('template');
		swatch_template.innerHTML = '<div class="swatch"></div>';
		this.swatches.forEach(color => {
			let swatch = swatch_template.content.firstElementChild.cloneNode(true);
			this.swatches_wrapper.appendChild(swatch);
			swatch.addEventListener('click', () => {
				this.color = color;
				this.set_selector_position();
				this.update_color_map();
			});
			swatch.style.backgroundColor = color;
		});
	}

	set_selector_position() {
		this.hue = utils.get_hue(this.color);
		this.color_selector_position = this.get_pointer_coords();
		this.hue_selector_position = {
			x: this.hue * this.hue_map.offsetWidth / 360,
			y: this.hue_map.offsetHeight / 2
		};
		this.update_color_selector();
		this.update_hue_selector();
	}

	setup_color_event() {
		let on_drag = (x, y) => {
			this.color_selector_position.x = x;
			this.color_selector_position.y = y;
			this.update_color();
			this.update_color_selector();
		};
		this.setup_drag_event(this.color_map, on_drag);
	}

	update_color() {
		let x = this.color_selector_position.x;
		let y = this.color_selector_position.y;
		let w = this.color_map.offsetWidth;
		let h = this.color_map.offsetHeight;
		this.color = utils.hsv_to_hex(
			this.hue,
			Math.round(x / w * 100),
			Math.round((1 - (y / h)) * 100),
		);
	}

	update_color_selector() {
		let x = this.color_selector_position.x;
		let y = this.color_selector_position.y;
		// set color selector position and background
		this.color_selector_circle.style.top = (y - this.color_selector_circle.offsetHeight / 2) + 'px';
		this.color_selector_circle.style.left = (x - this.color_selector_circle.offsetWidth / 2) + 'px';
		this.color_map.style.color = this.color;
		this.on_change && this.on_change(this.color);
	}

	setup_hue_event() {
		let on_drag = (x, y) => {
			this.hue_selector_position.x = x;
			this.hue = Math.round(x * 360 / this.hue_map.offsetWidth);
			this.update_color_map();
			this.update_hue_selector();
			this.update_color();
			this.update_color_selector();
		};
		this.setup_drag_event(this.hue_map, on_drag);
	}

	update_color_map() {
		this.color_map.style.background = `
			linear-gradient(0deg, black, transparent),
			linear-gradient(90deg, white, transparent),
			hsl(${this.hue}, 100%, 50%)
		`;
	}

	update_hue_selector() {
		let x = this.hue_selector_position.x - 1;
		let y = (this.hue_map.offsetHeight / 2) - 1;
		// set color selector position and background
		this.hue_selector_circle.style.top = (y - this.hue_selector_circle.offsetHeight / 2) + 'px';
		this.hue_selector_circle.style.left = (x - this.hue_selector_circle.offsetWidth / 2) + 'px';
		this.hue_map.style.color = `hsl(${this.hue}, 100%, 50%)`;
	}

	get_pointer_coords() {
		let h, s, v;
		[h, s, v] = utils.get_hsv(this.color);
		let width = this.color_map.offsetWidth;
		let height = this.color_map.offsetHeight;
		let x = utils.clamp(0, s * width / 100, width);
		let y = utils.clamp(0, (1 - v * height) / 100, height);
		return {x, y};
	}

	setup_drag_event(element, callback) {
		let on_drag = (event, force) => {
			if (element.drag_enabled || force) {
				event.preventDefault();
				event = event.touches ? event.touches[0] : event;
				let element_bounds = element.getBoundingClientRect();
				let x = event.pageX - element_bounds.left;
				let y = event.pageY - element_bounds.top;
				x = utils.clamp(0, x, element_bounds.width);
				y = utils.clamp(0, y, element_bounds.height);
				callback(x, y);
			}
		};

		element.addEventListener("mousedown", () => element.drag_enabled = true);
		document.addEventListener("mouseup", () => element.drag_enabled = false);
		document.addEventListener("mousemove", on_drag);
		element.addEventListener("click", (event) => on_drag(event, true));

		element.addEventListener("touchstart", () => element.drag_enabled = true);
		element.addEventListener("touchend", () => element.drag_enabled = false);
		element.addEventListener("touchcancel", () => element.drag_enabled = false);
		element.addEventListener("touchmove", (event) => {
			if (event.touches.length == 1) {
				on_drag(event);
			} else {
				element.drag_enabled = false;
			}
		});
	}
}

export default Picker;

// window.picker = new Picker({
// 	parent: document.body,
// 	width: 210,
// 	height: 140,
// 	color: '#5f5387',
// 	swatches: [
// 		'#449CF0',
// 		'#ECAD4B',
// 		'#29CD42',
// 		'#761ACB',
// 		'#CB2929',
// 		'#ED6396',
// 		'#29CD42',
// 		'#4463F0',
// 		'#EC864B',
// 		'#4F9DD9',
// 		'#39E4A5',
// 		'#B4CD29',
// 	]
// });

// picker.on_change = (color) => {
// 	document.body.style.backgroundColor = color;
// };