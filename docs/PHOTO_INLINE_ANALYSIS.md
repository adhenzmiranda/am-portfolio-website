# How ProjectPhoto Inline Works - Analysis

## Current Working Setup

### 1. Model Definition (`projects/models.py`)

```python
class ProjectPhoto(models.Model):
    project = models.ForeignKey(Projects, on_delete=models.CASCADE, related_name='photos')
    image = CloudinaryField('image', folder='project_photos',
        transformation=[
            {'width': 1920, 'height': 1080, 'crop': 'limit'},
            {'quality': 'auto', 'fetch_format': 'auto'}
        ])
    caption = models.CharField(max_length=200, blank=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
```

**Key Points:**

- Uses `CloudinaryField` for image storage
- Simple field definition, nothing special
- No custom upload processing

---

### 2. Admin Inline Setup (`projects/admin.py`)

```python
class ProjectPhotoFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial = [{'order': i} for i in range(len(self.forms))]

class ProjectPhotoInline(admin.TabularInline):
    model = ProjectPhoto
    formset = ProjectPhotoFormSet
    extra = 5  # Shows 5 empty forms
    fields = ('image', 'caption', 'order')
    readonly_fields = ('created_at',)
    min_num = 0
    validate_min = False
    can_delete = True
    show_change_link = True
    template = 'admin/edit_inline/tabular.html'
```

**Key Points:**

- Uses `TabularInline` (displays as table)
- `extra = 5` means 5 empty rows show up
- Standard Django inline, no custom JavaScript
- Template: `admin/edit_inline/tabular.html` (Django's default)

---

### 3. How User Uploads Photos Currently

**Step-by-step process:**

1. User goes to `/admin/projects/projects/28/change/`
2. Scrolls to "Photos" section
3. Sees 5 empty rows (because `extra = 5`)
4. Each row has:
   - File input: "Choose File" button
   - Caption text field
   - Order number field
5. User clicks "Choose File" on Row 1 → Selects image1.jpg
6. User clicks "Choose File" on Row 2 → Selects image2.jpg
7. User clicks "Choose File" on Row 3 → Selects image3.jpg
8. User clicks "Save" button once
9. Django processes the form:
   - Creates 3 ProjectPhoto instances
   - Uploads each file to Cloudinary
   - Saves to database

**This works because:**

- Each "Choose File" is a separate form field
- User manually selects one file per row
- Django's formset handles saving multiple instances

---

## Why Batch Upload Isn't Working

### Problem 1: Button Not Appearing

- JavaScript tries to find `[id*="projectphoto_set"]`
- Selector might be wrong
- Need to inspect actual HTML to find correct selector

### Problem 2: Even if Button Works

- Can't assign multiple files to ONE input field
- Each inline row has its OWN file input
- Need to:
  1. Create NEW rows (click "Add another")
  2. Find the NEW file input in that row
  3. Assign ONE file to that input

### Problem 3: DataTransfer API

- `dataTransfer.items.add(file)` creates a FileList
- But Django's inline might not accept programmatically set files
- Browsers have security restrictions

---

## What User Actually Wants

**Current Process:**

- Click "Choose File" 5 times
- Select one file each time
- Click Save

**Desired Process:**

- Click ONE button "Select Multiple Photos"
- Select 5 files at once in file picker
- Files automatically populate into the 5 rows
- Click Save

---

## The Real Solution

### Option A: Use Native Browser Behavior (SIMPLEST)

**Don't use JavaScript. Just make the file input accept multiple files:**

But wait... Django inline creates SEPARATE forms. Can't use `multiple` attribute.

### Option B: Actually Check What Works

1. Open browser dev tools
2. Go to Projects admin edit page
3. Find the actual HTML structure of photo inline
4. Find the EXACT selector for:
   - The inline container
   - The "Add another" button
   - The file input fields
5. Write JavaScript that ACTUALLY works with these selectors

---

---

## ✅ ACTUAL HTML STRUCTURE (From Browser Inspector)

### Photos Inline Container:

```html
<div
  class="js-inline-admin-formset inline-group"
  id="photos-group"
  data-inline-type="tabular"
>
  <div class="tabular inline-related">
    <input
      type="hidden"
      name="photos-TOTAL_FORMS"
      value="50"
      id="id_photos-TOTAL_FORMS"
    />
    <input
      type="hidden"
      name="photos-INITIAL_FORMS"
      value="45"
      id="id_photos-INITIAL_FORMS"
    />

    <fieldset class="module">
      <h2 id="photos-heading" class="inline-heading">Project photos</h2>

      <table>
        <tbody>
          <!-- EXISTING PHOTOS (45 of them) -->
          <tr class="form-row has_original dynamic-photos" id="photos-0">
            <td class="field-image">
              <input type="file" name="photos-0-image" id="id_photos-0-image" />
            </td>
            <td class="field-caption">
              <input
                type="text"
                name="photos-0-caption"
                id="id_photos-0-caption"
              />
            </td>
            <td class="field-order">
              <input
                type="number"
                name="photos-0-order"
                value="0"
                id="id_photos-0-order"
              />
            </td>
          </tr>

          <!-- EMPTY FORMS (5 of them, because extra=5) -->
          <tr class="form-row dynamic-photos" id="photos-45">
            <td class="field-image">
              <input
                type="file"
                name="photos-45-image"
                id="id_photos-45-image"
              />
            </td>
            <td class="field-caption">
              <input
                type="text"
                name="photos-45-caption"
                id="id_photos-45-caption"
              />
            </td>
            <td class="field-order">
              <input
                type="number"
                name="photos-45-order"
                value="0"
                id="id_photos-45-order"
              />
            </td>
          </tr>

          <!-- ... 4 more empty rows (photos-46, photos-47, photos-48, photos-49) -->

          <!-- TEMPLATE ROW (hidden, used for adding new rows) -->
          <tr class="form-row empty-form" id="photos-empty">
            <td class="field-image">
              <input
                type="file"
                name="photos-__prefix__-image"
                id="id_photos-__prefix__-image"
              />
            </td>
            <!-- ... -->
          </tr>

          <!-- ADD BUTTON -->
          <tr class="add-row">
            <td colspan="5">
              <a role="button" class="addlink" href="#"
                >Add another Project photo</a
              >
            </td>
          </tr>
        </tbody>
      </table>
    </fieldset>
  </div>
</div>
```

### Key Selectors Found:

- **Main container**: `#photos-group` ✅
- **Add button**: `#photos-group .add-row a` ✅
- **Empty forms**: `#photos-group .dynamic-photos` ✅
- **File inputs**: `input[name*="photos"][name*="image"]` ✅
- **Total forms counter**: `#id_photos-TOTAL_FORMS` ✅

---

## 🔥 THE REAL PROBLEM

Looking at the custom template's JavaScript, I found it:

```javascript
// Find photo inline section
const photoInline = document.querySelector('[id*="projectphoto_set"]');
```

**This selector is WRONG!** The actual ID is `photos-group`, NOT `projectphoto_set`.

### What's Happening:

1. JavaScript looks for `[id*="projectphoto_set"]` → **FINDS NOTHING**
2. `if (photoInline)` → **FALSE**, so button never gets injected
3. No batch upload buttons appear at all

### The Fix:

Change selector from `[id*="projectphoto_set"]` to `#photos-group` (or `[id*="photos-group"]`)

Same issue with videos - it's looking for `projectvideo_set` but actual ID is `videos-group`.

---

## 🎯 CORRECT IMPLEMENTATION

```javascript
// Find photo inline section - USE CORRECT SELECTOR
const photoInline = document.querySelector("#photos-group");

if (photoInline) {
  // Inject button BEFORE the table, not inside it
  const fieldset = photoInline.querySelector("fieldset");

  const batchPhotoHTML = `
        <div style="background: #e8f5e9; padding: 15px; margin-bottom: 15px;">
            <input type="file" id="batchPhotoUpload" accept="image/*" multiple style="display: none;">
            <button type="button" onclick="document.getElementById('batchPhotoUpload').click()">
                📸 Select Multiple Photos
            </button>
        </div>
    `;

  // Insert BEFORE the fieldset
  fieldset.insertAdjacentHTML("beforebegin", batchPhotoHTML);
}

// Handle file selection
document.addEventListener("change", function (e) {
  if (e.target.id === "batchPhotoUpload") {
    const files = Array.from(e.target.files);
    const addButton = document.querySelector("#photos-group .add-row a");

    files.forEach((file, index) => {
      // Click "Add another" to create new row
      addButton.click();

      setTimeout(() => {
        // Find the LAST empty form
        const allForms = document.querySelectorAll(
          "#photos-group .dynamic-photos"
        );
        const lastForm = allForms[allForms.length - 1];

        // Find file input in that form
        const fileInput = lastForm.querySelector('input[type="file"]');

        // THIS IS THE CRITICAL PART
        const dataTransfer = new DataTransfer();
        dataTransfer.items.add(file);
        fileInput.files = dataTransfer.files;

        // Set caption
        const captionInput = lastForm.querySelector('input[name*="caption"]');
        if (captionInput) {
          captionInput.value = file.name.replace(/\.[^/.]+$/, "");
        }

        // Set order
        const orderInput = lastForm.querySelector('input[name*="order"]');
        if (orderInput) {
          orderInput.value = index;
        }
      }, index * 100);
    });
  }
});
```

---

## 🚨 CRITICAL ISSUES TO FIX

1. **Wrong selectors** - `projectphoto_set` doesn't exist, should be `photos-group`
2. **Wrong injection point** - Trying to inject inside inline-group, should inject before fieldset
3. **Form counter** - Need to update `photos-TOTAL_FORMS` hidden input after adding rows
4. **Timing** - Need proper delays between clicking "Add" buttons

---

## NEXT STEP

Update `templates/admin/projects/projects/change_form.html` with correct selectors.
